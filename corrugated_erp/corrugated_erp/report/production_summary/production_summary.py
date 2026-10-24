# Copyright (c) 2026, Syvasoft Business Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt

GROUPS = {
	"Stage": "pe.production_stage",
	"Machine": "pe.workstation",
	"Shift": "pe.shift",
	"Operator": "pe.operator_name",
	"Date": "pe.posting_date",
	"Work Order": "pe.work_order",
}


def execute(filters=None):
	filters = frappe._dict(filters or {})
	group_by = filters.get("group_by") or "Stage"
	key = GROUPS.get(group_by, "pe.production_stage")
	conditions = ["pe.docstatus = 1", "pe.posting_date between %(from_date)s and %(to_date)s"]
	for field in ("production_stage", "workstation", "work_order", "shift"):
		if filters.get(field):
			conditions.append("pe.{0} = %({0})s".format(field))
	rows = frappe.db.sql(
		"""select {key} as group_value, count(pe.name) as entries,
			sum(pe.output_qty) as output_qty, sum(pe.rejected_qty) as rejected_qty,
			sum(pe.duration_hrs) as hours, sum(pe.net_run_hrs) as run_hours, sum(pe.total_downtime_min) as downtime_min,
			sum(pe.box_equivalent) as box_equivalent, sum(pe.total_reel_consumed_kg) as paper_kg,
			sum(pe.total_waste_kg) as waste_kg, min(ps.sequence) as seq
		from `tabProduction Entry` pe
		left join `tabProduction Stage` ps on ps.name = pe.production_stage
		where {cond}
		group by {key}
		order by seq, group_value""".format(key=key, cond=" and ".join(conditions)),
		filters,
		as_dict=True,
	)
	for r in rows:
		made = flt(r.output_qty) + flt(r.rejected_qty)
		r.rejection_pct = flt(flt(r.rejected_qty) / made * 100, 2) if made else 0
		run = flt(r.run_hours) or flt(r.hours)
		r.output_per_hour = flt(flt(r.output_qty) / run, 1) if run else 0
		r.downtime_hrs = flt(flt(r.downtime_min) / 60.0, 1)
		r.availability_pct = flt(flt(r.run_hours) / flt(r.hours) * 100, 1) if flt(r.hours) and flt(r.run_hours) else None
		r.waste_pct = flt(flt(r.waste_kg) / flt(r.paper_kg) * 100, 2) if flt(r.paper_kg) else None

	columns = [
		{"label": _(group_by), "fieldname": "group_value", "fieldtype": "Data", "width": 170},
		{"label": _("Entries"), "fieldname": "entries", "fieldtype": "Int", "width": 80},
		{"label": _("Good Output"), "fieldname": "output_qty", "fieldtype": "Float", "width": 120},
		{"label": _("Rejected"), "fieldname": "rejected_qty", "fieldtype": "Float", "width": 100},
		{"label": _("Rejection %"), "fieldname": "rejection_pct", "fieldtype": "Percent", "width": 100},
		{"label": _("Box Equivalent"), "fieldname": "box_equivalent", "fieldtype": "Float", "width": 120},
		{"label": _("Hours"), "fieldname": "hours", "fieldtype": "Float", "width": 80},
		{"label": _("Downtime (hrs)"), "fieldname": "downtime_hrs", "fieldtype": "Float", "width": 110},
		{"label": _("Availability %"), "fieldname": "availability_pct", "fieldtype": "Percent", "width": 110},
		{"label": _("Output / Running Hour"), "fieldname": "output_per_hour", "fieldtype": "Float", "width": 150},
		{"label": _("Paper Used (kg)"), "fieldname": "paper_kg", "fieldtype": "Float", "width": 120},
		{"label": _("Waste (kg)"), "fieldname": "waste_kg", "fieldtype": "Float", "width": 100},
		{"label": _("Waste % of Paper"), "fieldname": "waste_pct", "fieldtype": "Percent", "width": 120},
	]
	chart = None
	if rows:
		chart = {
			"data": {
				"labels": [str(r.group_value or _("Not Set")) for r in rows],
				"datasets": [
					{"name": _("Good Output"), "values": [flt(r.output_qty) for r in rows]},
					{"name": _("Rejected"), "values": [flt(r.rejected_qty) for r in rows]},
				],
			},
			"type": "bar",
			"barOptions": {"stacked": 1},
		}
	return columns, rows, None, chart
