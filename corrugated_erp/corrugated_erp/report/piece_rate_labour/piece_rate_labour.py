# Copyright (c) 2026, Syvasoft Business Solutions and contributors
# For license information, please see license.txt

"""Contract labour earned by piece rate, per contractor / operator and stage, for payment."""

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = frappe._dict(filters or {})
	cond = ["pe.docstatus = 1", "pe.posting_date between %(from_date)s and %(to_date)s", "pe.labour_amount > 0"]
	for field in ("contractor", "operator", "production_stage", "company"):
		if filters.get(field):
			cond.append("pe.{0} = %({0})s".format(field))
	detail = filters.get("show_entries")
	if detail:
		rows = frappe.db.sql(
			"""select pe.posting_date, pe.name production_entry, pe.contractor, pe.operator_name, pe.production_stage,
				pe.work_order, pe.output_qty, pe.piece_rate, pe.piece_rate_basis, pe.labour_amount
			from `tabProduction Entry` pe where {0}
			order by pe.contractor, pe.operator_name, pe.posting_date""".format(" and ".join(cond)),
			filters,
			as_dict=True,
		)
	else:
		rows = frappe.db.sql(
			"""select pe.contractor, pe.operator_name, pe.production_stage, count(pe.name) entries,
				sum(pe.output_qty) output_qty, sum(pe.labour_amount) labour_amount
			from `tabProduction Entry` pe where {0}
			group by pe.contractor, pe.operator_name, pe.production_stage
			order by pe.contractor, pe.operator_name, pe.production_stage""".format(" and ".join(cond)),
			filters,
			as_dict=True,
		)
	columns = []
	if detail:
		columns += [
			{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 95},
			{"label": _("Production Entry"), "fieldname": "production_entry", "fieldtype": "Link", "options": "Production Entry", "width": 140},
		]
	columns += [
		{"label": _("Contractor"), "fieldname": "contractor", "fieldtype": "Link", "options": "Supplier", "width": 160},
		{"label": _("Operator"), "fieldname": "operator_name", "fieldtype": "Data", "width": 140},
		{"label": _("Stage"), "fieldname": "production_stage", "fieldtype": "Link", "options": "Production Stage", "width": 140},
	]
	if detail:
		columns += [
			{"label": _("Work Order"), "fieldname": "work_order", "fieldtype": "Link", "options": "Work Order", "width": 140},
			{"label": _("Output"), "fieldname": "output_qty", "fieldtype": "Float", "width": 100},
			{"label": _("Rate"), "fieldname": "piece_rate", "fieldtype": "Currency", "width": 90},
			{"label": _("Basis"), "fieldname": "piece_rate_basis", "fieldtype": "Data", "width": 110},
		]
	else:
		columns += [
			{"label": _("Entries"), "fieldname": "entries", "fieldtype": "Int", "width": 80},
			{"label": _("Output"), "fieldname": "output_qty", "fieldtype": "Float", "width": 110},
		]
	columns.append({"label": _("Amount"), "fieldname": "labour_amount", "fieldtype": "Currency", "width": 120})
	total = sum(flt(r.labour_amount) for r in rows)
	summary = [{"label": _("Total Labour Payable"), "value": total, "datatype": "Currency", "indicator": "Blue"}]
	return columns, rows, None, None, summary
