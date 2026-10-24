# Copyright (c) 2026, Syvasoft Business Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt

GROUPS = {
	"Reason": "d.reason",
	"Machine": "pe.workstation",
	"Stage": "pe.production_stage",
	"Shift": "pe.shift",
	"Date": "pe.posting_date",
}


def execute(filters=None):
	filters = frappe._dict(filters or {})
	group_by = filters.get("group_by") or "Reason"
	key = GROUPS.get(group_by, "d.reason")
	cond = ["pe.docstatus = 1", "pe.posting_date between %(from_date)s and %(to_date)s"]
	for field in ("workstation", "production_stage", "shift"):
		if filters.get(field):
			cond.append("pe.{0} = %({0})s".format(field))
	if filters.get("reason"):
		cond.append("d.reason = %(reason)s")
	rows = frappe.db.sql(
		"""select {key} as group_value, count(d.name) as occurrences, sum(d.minutes) as minutes,
			count(distinct pe.name) as entries
		from `tabProduction Entry Downtime` d
		join `tabProduction Entry` pe on pe.name = d.parent and d.parenttype = 'Production Entry'
		where {cond}
		group by {key}
		order by minutes desc""".format(key=key, cond=" and ".join(cond)),
		filters,
		as_dict=True,
	)
	shift_hours = flt(
		frappe.db.sql(
			"""select sum(pe.duration_hrs) from `tabProduction Entry` pe where {0}""".format(
				" and ".join(c for c in cond if not c.startswith("d."))
			),
			filters,
		)[0][0]
	)
	total = sum(flt(r.minutes) for r in rows)
	for r in rows:
		r.hours = flt(flt(r.minutes) / 60.0, 2)
		r.share_pct = flt(flt(r.minutes) / total * 100, 1) if total else 0
		r.pct_of_shift = flt(flt(r.minutes) / 60.0 / shift_hours * 100, 1) if shift_hours else None
	columns = [
		{"label": _(group_by), "fieldname": "group_value", "fieldtype": "Data", "width": 200},
		{"label": _("Times"), "fieldname": "occurrences", "fieldtype": "Int", "width": 80},
		{"label": _("Minutes"), "fieldname": "minutes", "fieldtype": "Float", "width": 100},
		{"label": _("Hours"), "fieldname": "hours", "fieldtype": "Float", "width": 90},
		{"label": _("Share of Downtime %"), "fieldname": "share_pct", "fieldtype": "Percent", "width": 150},
		{"label": _("% of Shift Time"), "fieldname": "pct_of_shift", "fieldtype": "Percent", "width": 120},
		{"label": _("Production Entries"), "fieldname": "entries", "fieldtype": "Int", "width": 130},
	]
	chart = None
	if rows:
		chart = {
			"data": {"labels": [str(r.group_value) for r in rows[:12]], "datasets": [{"name": _("Hours"), "values": [r.hours for r in rows[:12]]}]},
			"type": "bar",
		}
	summary = [
		{"label": _("Total Downtime (hrs)"), "value": flt(total / 60.0, 1), "indicator": "Red"},
		{"label": _("Shift Hours Booked"), "value": flt(shift_hours, 1), "indicator": "Blue"},
	]
	return columns, rows, None, chart, summary
