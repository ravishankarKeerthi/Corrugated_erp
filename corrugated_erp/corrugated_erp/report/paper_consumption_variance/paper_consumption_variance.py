# Copyright (c) 2026, Syvasoft Business Solutions and contributors
# For license information, please see license.txt

"""Standard vs actual paper per Work Order.

Standard paper = boxes produced x box weight (from the Box Specification) x (1 + process waste %).
Actual paper   = kg consumed from reels in Production Entries for the Work Order.
"""

import frappe
from frappe import _
from frappe.utils import flt

from corrugated_erp.utils.common import get_settings


def execute(filters=None):
	filters = frappe._dict(filters or {})
	waste = 1 + flt(get_settings().process_waste_pct) / 100.0
	conditions = ["wo.docstatus = 1", "ifnull(wo.box_spec, '') != ''", "wo.planned_start_date between %(from_date)s and %(to_date)s"]
	if filters.get("customer"):
		conditions.append("spec.customer = %(customer)s")
	if filters.get("status"):
		conditions.append("wo.status = %(status)s")
	rows = frappe.db.sql(
		"""select wo.name as work_order, wo.status, wo.production_item, spec.name as box_spec, spec.customer,
			wo.qty, wo.produced_qty, spec.box_weight_g,
			(select sum(pe.total_reel_consumed_kg) from `tabProduction Entry` pe
				where pe.work_order = wo.name and pe.docstatus = 1) as actual_kg
		from `tabWork Order` wo
		join `tabBox Specification` spec on spec.name = wo.box_spec
		where {0}
		order by wo.planned_start_date desc""".format(" and ".join(conditions)),
		filters,
		as_dict=True,
	)
	data = []
	for r in rows:
		r.standard_kg = flt(flt(r.produced_qty) * flt(r.box_weight_g) / 1000.0 * waste, 2)
		r.actual_kg = flt(r.actual_kg, 2)
		r.variance_kg = flt(r.actual_kg - r.standard_kg, 2)
		r.variance_pct = flt(r.variance_kg / r.standard_kg * 100, 2) if r.standard_kg else None
		r.actual_g_per_box = flt(r.actual_kg * 1000 / flt(r.produced_qty), 1) if flt(r.produced_qty) else None
		if filters.get("only_over") and not (r.variance_kg > 0):
			continue
		data.append(r)

	columns = [
		{"label": _("Work Order"), "fieldname": "work_order", "fieldtype": "Link", "options": "Work Order", "width": 140},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
		{"label": _("Box"), "fieldname": "production_item", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 140},
		{"label": _("Produced"), "fieldname": "produced_qty", "fieldtype": "Float", "width": 90},
		{"label": _("Std Box Wt (g)"), "fieldname": "box_weight_g", "fieldtype": "Float", "width": 110},
		{"label": _("Actual g / Box"), "fieldname": "actual_g_per_box", "fieldtype": "Float", "width": 110},
		{"label": _("Standard Paper (kg)"), "fieldname": "standard_kg", "fieldtype": "Float", "width": 140},
		{"label": _("Actual Paper (kg)"), "fieldname": "actual_kg", "fieldtype": "Float", "width": 130},
		{"label": _("Variance (kg)"), "fieldname": "variance_kg", "fieldtype": "Float", "width": 110},
		{"label": _("Variance %"), "fieldname": "variance_pct", "fieldtype": "Percent", "width": 100},
	]
	over = sum(flt(r.variance_kg) for r in data if flt(r.variance_kg) > 0)
	summary = [
		{"label": _("Work Orders"), "value": len(data), "datatype": "Int", "indicator": "Blue"},
		{"label": _("Excess Paper (kg)"), "value": flt(over, 0), "datatype": "Float", "indicator": "Red" if over else "Green"},
	]
	return columns, data, _("Standard includes {0}% process waste from Corrugation Settings").format(flt((waste - 1) * 100, 2)), None, summary
