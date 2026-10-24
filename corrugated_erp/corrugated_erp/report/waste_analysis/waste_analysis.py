# Copyright (c) 2026, Syvasoft Business Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = frappe._dict(filters or {})
	conditions = ["pe.docstatus = 1", "pe.posting_date between %(from_date)s and %(to_date)s"]
	for field in ("production_stage", "workstation"):
		if filters.get(field):
			conditions.append("pe.{0} = %({0})s".format(field))
	where = " and ".join(conditions)
	rows = frappe.db.sql(
		"""select w.waste_type, pe.production_stage, pe.workstation, sum(w.qty_kg) as qty_kg, count(distinct pe.name) as entries
		from `tabProduction Entry` pe
		join `tabProduction Entry Waste` w on w.parent = pe.name and w.parenttype = 'Production Entry'
		where {0}
		group by w.waste_type, pe.production_stage, pe.workstation
		order by qty_kg desc""".format(where),
		filters,
		as_dict=True,
	)
	paper = flt(
		frappe.db.sql(
			"select sum(pe.total_reel_consumed_kg) from `tabProduction Entry` pe where {0}".format(where), filters
		)[0][0]
	)
	total = sum(flt(r.qty_kg) for r in rows)
	for r in rows:
		r.share_pct = flt(flt(r.qty_kg) / total * 100, 2) if total else 0
		r.pct_of_paper = flt(flt(r.qty_kg) / paper * 100, 2) if paper else None

	columns = [
		{"label": _("Waste Type"), "fieldname": "waste_type", "fieldtype": "Data", "width": 150},
		{"label": _("Stage"), "fieldname": "production_stage", "fieldtype": "Link", "options": "Production Stage", "width": 150},
		{"label": _("Machine"), "fieldname": "workstation", "fieldtype": "Link", "options": "Workstation", "width": 140},
		{"label": _("Entries"), "fieldname": "entries", "fieldtype": "Int", "width": 80},
		{"label": _("Waste (kg)"), "fieldname": "qty_kg", "fieldtype": "Float", "width": 110},
		{"label": _("Share of Waste %"), "fieldname": "share_pct", "fieldtype": "Percent", "width": 130},
		{"label": _("% of Paper Used"), "fieldname": "pct_of_paper", "fieldtype": "Percent", "width": 130},
	]
	by_type = {}
	for r in rows:
		by_type[r.waste_type] = by_type.get(r.waste_type, 0) + flt(r.qty_kg)
	chart = (
		{
			"data": {"labels": list(by_type), "datasets": [{"name": _("Waste kg"), "values": [flt(v, 1) for v in by_type.values()]}]},
			"type": "donut",
		}
		if by_type
		else None
	)
	summary = [
		{"label": _("Paper Used (kg)"), "value": flt(paper, 0), "datatype": "Float", "indicator": "Blue"},
		{"label": _("Total Waste (kg)"), "value": flt(total, 0), "datatype": "Float", "indicator": "Orange"},
		{
			"label": _("Waste % of Paper"),
			"value": flt(total / paper * 100, 2) if paper else 0,
			"datatype": "Percent",
			"indicator": "Red" if paper and total / paper > 0.05 else "Green",
		},
	]
	return columns, rows, None, chart, summary
