# Copyright (c) 2026, Syvasoft Business Solutions and contributors
# For license information, please see license.txt

"""Latest costing for every active box with the paper cost re-priced at today's paper rates,
so margin erosion after paper price increases is visible before quoting again."""

import frappe
from frappe import _
from frappe.utils import flt

from corrugated_erp.utils import corrugation as calc
from corrugated_erp.utils.common import get_paper_rate


def execute(filters=None):
	filters = frappe._dict(filters or {})
	spec_filters = {"status": "Active", "latest_costing": ["is", "set"]}
	if filters.get("customer"):
		spec_filters["customer"] = filters.customer
	specs = frappe.get_all(
		"Box Specification",
		filters=spec_filters,
		fields=["name", "box_name", "customer", "ply", "box_weight_g", "latest_costing"],
	)
	rate_cache = {}
	data = []
	for spec in specs:
		costing = frappe.get_doc("Box Costing", spec.latest_costing)
		current = {}
		for p in costing.papers:
			if p.paper_item and p.paper_item not in rate_cache:
				rate_cache[p.paper_item] = get_paper_rate(p.paper_item)
			if p.paper_item:
				current[p.paper_item] = rate_cache[p.paper_item] or p.rate
		now = calc.compute_cost(costing.cost_inputs(current))
		price = flt(costing.final_price_per_box)
		row = {
			"box_spec": spec.name,
			"box_name": spec.box_name,
			"customer": spec.customer,
			"ply": spec.ply,
			"box_weight_g": spec.box_weight_g,
			"box_costing": costing.name,
			"costing_date": costing.costing_date,
			"price_per_box": price,
			"costed_cost_per_box": costing.total_cost_per_box,
			"costed_margin_pct": costing.achieved_margin_pct,
			"current_cost_per_box": now["total_cost_per_box"],
			"current_margin_pct": calc.achieved_margin_pct(price, now["total_cost_per_box"]),
			"price_per_kg": flt(price / (flt(spec.box_weight_g) / 1000.0), 2) if flt(spec.box_weight_g) else 0,
		}
		row["margin_drop"] = flt(flt(row["costed_margin_pct"]) - flt(row["current_margin_pct"]), 2)
		if filters.get("below_margin") and row["current_margin_pct"] >= flt(filters.below_margin):
			continue
		data.append(row)
	data.sort(key=lambda r: r["current_margin_pct"])

	columns = [
		{"label": _("Box Spec"), "fieldname": "box_spec", "fieldtype": "Link", "options": "Box Specification", "width": 110},
		{"label": _("Box"), "fieldname": "box_name", "fieldtype": "Data", "width": 180},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 150},
		{"label": _("Ply"), "fieldname": "ply", "fieldtype": "Data", "width": 50},
		{"label": _("Box Wt (g)"), "fieldname": "box_weight_g", "fieldtype": "Float", "width": 90},
		{"label": _("Costing"), "fieldname": "box_costing", "fieldtype": "Link", "options": "Box Costing", "width": 130},
		{"label": _("Costed On"), "fieldname": "costing_date", "fieldtype": "Date", "width": 95},
		{"label": _("Price / Box"), "fieldname": "price_per_box", "fieldtype": "Currency", "width": 100},
		{"label": _("Price / Kg"), "fieldname": "price_per_kg", "fieldtype": "Currency", "width": 95},
		{"label": _("Cost then"), "fieldname": "costed_cost_per_box", "fieldtype": "Currency", "width": 100},
		{"label": _("Margin then %"), "fieldname": "costed_margin_pct", "fieldtype": "Percent", "width": 110},
		{"label": _("Cost today"), "fieldname": "current_cost_per_box", "fieldtype": "Currency", "width": 100},
		{"label": _("Margin today %"), "fieldname": "current_margin_pct", "fieldtype": "Percent", "width": 115},
		{"label": _("Margin Drop %"), "fieldname": "margin_drop", "fieldtype": "Float", "width": 110},
	]
	return columns, data
