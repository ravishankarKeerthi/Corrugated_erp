# Copyright (c) 2026, Syvasoft Business Solutions and contributors
# For license information, please see license.txt

"""Where each open box job is lying: boxes (sheet output x ups) completed at every stage,
and the quantity waiting between stages."""

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = frappe._dict(filters or {})
	stages = frappe.get_all(
		"Production Stage", filters={"is_active": 1}, fields=["name", "sequence"], order_by="sequence asc"
	)
	wo_filters = {"docstatus": 1, "status": ["in", ["Not Started", "In Process"]], "box_spec": ["is", "set"]}
	if filters.get("company"):
		wo_filters["company"] = filters.company
	if filters.get("customer"):
		specs = frappe.get_all("Box Specification", filters={"customer": filters.customer}, pluck="name")
		wo_filters["box_spec"] = ["in", specs or [""]]
	work_orders = frappe.get_all(
		"Work Order",
		filters=wo_filters,
		fields=["name", "production_item", "item_name", "box_spec", "qty", "produced_qty", "planned_start_date", "sales_order"],
		order_by="planned_start_date asc",
	)
	done = {}
	if work_orders:
		for r in frappe.db.sql(
			"""select work_order, production_stage, sum(box_equivalent) qty from `tabProduction Entry`
			where docstatus = 1 and work_order in %(wos)s group by work_order, production_stage""",
			{"wos": [w.name for w in work_orders]},
			as_dict=True,
		):
			done[(r.work_order, r.production_stage)] = flt(r.qty)
	data = []
	for wo in work_orders:
		row = {
			"work_order": wo.name,
			"customer": frappe.db.get_value("Box Specification", wo.box_spec, "customer"),
			"item_name": wo.item_name,
			"qty": wo.qty,
			"produced_qty": wo.produced_qty,
			"planned_start_date": wo.planned_start_date,
		}
		used = [s for s in stages if (wo.name, s.name) in done]
		waiting = []
		for i, s in enumerate(stages):
			row[frappe.scrub(s.name)] = done.get((wo.name, s.name))
		for i, s in enumerate(used):
			nxt = used[i + 1] if i + 1 < len(used) else None
			after = done[(wo.name, s.name)] - (done[(wo.name, nxt.name)] if nxt else flt(wo.produced_qty))
			if after > 0.5:
				waiting.append("{0}: {1}".format(s.name, int(after)))
		row["waiting_after"] = ", ".join(waiting)
		row["not_started"] = max(flt(wo.qty) - (done[(wo.name, used[0].name)] if used else 0), 0)
		data.append(row)
	columns = [
		{"label": _("Work Order"), "fieldname": "work_order", "fieldtype": "Link", "options": "Work Order", "width": 150},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 150},
		{"label": _("Box"), "fieldname": "item_name", "fieldtype": "Data", "width": 170},
		{"label": _("Order Qty"), "fieldname": "qty", "fieldtype": "Float", "width": 90},
		{"label": _("Not Started"), "fieldname": "not_started", "fieldtype": "Float", "width": 95},
	]
	for s in stages:
		columns.append({"label": s.name, "fieldname": frappe.scrub(s.name), "fieldtype": "Float", "width": 105})
	columns += [
		{"label": _("Finished (Stock)"), "fieldname": "produced_qty", "fieldtype": "Float", "width": 110},
		{"label": _("Waiting After"), "fieldname": "waiting_after", "fieldtype": "Data", "width": 260},
		{"label": _("Planned Start"), "fieldname": "planned_start_date", "fieldtype": "Datetime", "width": 140},
	]
	return columns, data
