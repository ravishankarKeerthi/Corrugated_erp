# Copyright (c) 2026, Syvasoft Business Solutions and contributors
# For license information, please see license.txt

"""Did each box job make money?

Revenue      = boxes produced x sales order rate (or the latest costing price when there is no order)
Material     = ACTUAL value of paper, gum, ink etc. transferred to the Work Order
Conversion   = STANDARD conversion, printing, stitching, tooling and overhead per box from the costing
Contract labour and downtime are shown for information (conversion already includes labour).
"""

import frappe
from frappe import _
from frappe.utils import flt

from corrugated_erp.utils.common import get_settings


def execute(filters=None):
	filters = frappe._dict(filters or {})
	cond = ["wo.docstatus = 1", "wo.box_spec is not null", "wo.produced_qty > 0"]
	if filters.get("from_date"):
		cond.append("date(coalesce(wo.actual_end_date, wo.modified)) >= %(from_date)s")
	if filters.get("to_date"):
		cond.append("date(coalesce(wo.actual_end_date, wo.modified)) <= %(to_date)s")
	if filters.get("company"):
		cond.append("wo.company = %(company)s")
	if filters.get("status"):
		cond.append("wo.status = %(status)s")
	if filters.get("customer"):
		cond.append("bs.customer = %(customer)s")
	wos = frappe.db.sql(
		"""select wo.name, wo.production_item, wo.item_name, wo.box_spec, wo.qty, wo.produced_qty, wo.sales_order,
			wo.company, wo.status, bs.customer, bs.box_weight_g, bs.latest_costing
		from `tabWork Order` wo join `tabBox Specification` bs on bs.name = wo.box_spec
		where {0} order by wo.modified desc""".format(" and ".join(cond)),
		filters,
		as_dict=True,
	)
	data = []
	for wo in wos:
		produced = flt(wo.produced_qty)
		price = so_rate(wo)
		costing = (
			frappe.db.get_value(
				"Box Costing",
				wo.latest_costing,
				[
					"final_price_per_box", "total_cost_per_box", "paper_cost_per_box", "waste_cost_per_box", "gum_cost_per_box",
					"achieved_margin_pct",
				],
				as_dict=True,
			)
			if wo.latest_costing
			else None
		) or frappe._dict()
		if not price:
			price = flt(costing.final_price_per_box)
		material = flt(
			frappe.db.sql(
				"""select sum(sed.amount) from `tabStock Entry Detail` sed join `tabStock Entry` se on se.name = sed.parent
				where se.work_order = %s and se.docstatus = 1 and se.purpose = 'Material Transfer for Manufacture'""",
				wo.name,
			)[0][0]
		)
		pe = frappe.db.sql(
			"""select sum(total_reel_consumed_kg) paper_kg, sum(total_waste_kg) waste_kg, sum(labour_amount) labour,
				sum(total_downtime_min) downtime_min
			from `tabProduction Entry` where work_order = %s and docstatus = 1""",
			wo.name,
			as_dict=True,
		)[0]
		std_material_per_box = flt(costing.paper_cost_per_box) + flt(costing.waste_cost_per_box) + flt(costing.gum_cost_per_box)
		conversion_per_box = max(flt(costing.total_cost_per_box) - std_material_per_box, 0)
		conversion = conversion_per_box * produced
		revenue = price * produced
		total_cost = material + conversion
		margin = revenue - total_cost
		waste_pct = flt(get_settings(wo.company).process_waste_pct)
		std_paper_kg = produced * flt(wo.box_weight_g) / 1000.0 * (1 + waste_pct / 100.0)
		data.append(
			{
				"work_order": wo.name,
				"customer": wo.customer,
				"item_name": wo.item_name,
				"status": wo.status,
				"produced_qty": produced,
				"price_per_box": price,
				"revenue": flt(revenue, 2),
				"paper_kg": flt(pe.paper_kg, 1),
				"std_paper_kg": flt(std_paper_kg, 1),
				"paper_variance_pct": flt((flt(pe.paper_kg) / std_paper_kg - 1) * 100, 1) if std_paper_kg and flt(pe.paper_kg) else None,
				"material_cost": flt(material, 2),
				"conversion_cost": flt(conversion, 2),
				"total_cost": flt(total_cost, 2),
				"margin": flt(margin, 2),
				"margin_pct": flt(margin / total_cost * 100, 2) if total_cost else None,
				"quoted_margin_pct": costing.achieved_margin_pct,
				"labour": flt(pe.labour, 2),
				"waste_kg": flt(pe.waste_kg, 1),
				"downtime_hrs": flt(flt(pe.downtime_min) / 60.0, 1),
			}
		)
	columns = [
		{"label": _("Work Order"), "fieldname": "work_order", "fieldtype": "Link", "options": "Work Order", "width": 140},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 140},
		{"label": _("Box"), "fieldname": "item_name", "fieldtype": "Data", "width": 160},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 90},
		{"label": _("Produced"), "fieldname": "produced_qty", "fieldtype": "Float", "width": 90},
		{"label": _("Price / Box"), "fieldname": "price_per_box", "fieldtype": "Currency", "width": 95},
		{"label": _("Revenue"), "fieldname": "revenue", "fieldtype": "Currency", "width": 110},
		{"label": _("Paper Used (kg)"), "fieldname": "paper_kg", "fieldtype": "Float", "width": 110},
		{"label": _("Std Paper (kg)"), "fieldname": "std_paper_kg", "fieldtype": "Float", "width": 105},
		{"label": _("Paper Var %"), "fieldname": "paper_variance_pct", "fieldtype": "Percent", "width": 95},
		{"label": _("Material (Actual)"), "fieldname": "material_cost", "fieldtype": "Currency", "width": 125},
		{"label": _("Conversion (Std)"), "fieldname": "conversion_cost", "fieldtype": "Currency", "width": 120},
		{"label": _("Total Cost"), "fieldname": "total_cost", "fieldtype": "Currency", "width": 110},
		{"label": _("Margin"), "fieldname": "margin", "fieldtype": "Currency", "width": 110},
		{"label": _("Margin %"), "fieldname": "margin_pct", "fieldtype": "Percent", "width": 85},
		{"label": _("Quoted Margin %"), "fieldname": "quoted_margin_pct", "fieldtype": "Percent", "width": 115},
		{"label": _("Contract Labour"), "fieldname": "labour", "fieldtype": "Currency", "width": 115},
		{"label": _("Waste (kg)"), "fieldname": "waste_kg", "fieldtype": "Float", "width": 90},
		{"label": _("Downtime (hrs)"), "fieldname": "downtime_hrs", "fieldtype": "Float", "width": 105},
	]
	message = _(
		"Material is the actual value transferred to each Work Order. Conversion, printing, tooling and overhead are the standard per box from the Box Costing."
	)
	return columns, data, message


def so_rate(wo):
	"""Net rate per box (stock UOM) on the Sales Order line for this item."""
	if not wo.sales_order:
		return 0
	row = frappe.db.get_value(
		"Sales Order Item",
		{"parent": wo.sales_order, "item_code": wo.production_item},
		["base_net_rate", "conversion_factor"],
		as_dict=True,
	)
	if not row:
		return 0
	return flt(row.base_net_rate) / (flt(row.conversion_factor) or 1)
