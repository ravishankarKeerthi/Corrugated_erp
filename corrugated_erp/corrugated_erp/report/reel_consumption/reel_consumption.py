# Copyright (c) 2026, Syvasoft Business Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = frappe._dict(filters or {})
	conditions = ["pe.docstatus = 1", "pe.posting_date between %(from_date)s and %(to_date)s"]
	for field in ("work_order", "box_spec", "workstation"):
		if filters.get(field):
			conditions.append("pe.{0} = %({0})s".format(field))
	if filters.get("paper_item"):
		conditions.append("r.paper_item = %(paper_item)s")
	data = frappe.db.sql(
		"""select pe.posting_date, pe.name as production_entry, pe.shift, pe.workstation, pe.work_order,
			pe.box_spec, pe.production_item, r.paper_reel, r.layer, r.paper_item, r.deckle_mm,
			r.opening_weight, r.closing_weight, r.consumed_kg
		from `tabProduction Entry` pe
		join `tabProduction Entry Reel` r on r.parent = pe.name and r.parenttype = 'Production Entry'
		where {0}
		order by pe.posting_date, pe.name, r.idx""".format(" and ".join(conditions)),
		filters,
		as_dict=True,
	)
	total = sum(flt(d.consumed_kg) for d in data)
	summary = [
		{"label": _("Reels Used"), "value": len({d.paper_reel for d in data}), "datatype": "Int", "indicator": "Blue"},
		{"label": _("Paper Consumed (kg)"), "value": flt(total, 0), "datatype": "Float", "indicator": "Green"},
	]
	return get_columns(), data, None, None, summary


def get_columns():
	return [
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 95},
		{"label": _("Production Entry"), "fieldname": "production_entry", "fieldtype": "Link", "options": "Production Entry", "width": 140},
		{"label": _("Shift"), "fieldname": "shift", "fieldtype": "Data", "width": 70},
		{"label": _("Machine"), "fieldname": "workstation", "fieldtype": "Link", "options": "Workstation", "width": 120},
		{"label": _("Work Order"), "fieldname": "work_order", "fieldtype": "Link", "options": "Work Order", "width": 140},
		{"label": _("Box"), "fieldname": "production_item", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": _("Reel"), "fieldname": "paper_reel", "fieldtype": "Link", "options": "Paper Reel", "width": 130},
		{"label": _("Layer"), "fieldname": "layer", "fieldtype": "Data", "width": 100},
		{"label": _("Paper Item"), "fieldname": "paper_item", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": _("Deckle (mm)"), "fieldname": "deckle_mm", "fieldtype": "Float", "width": 95},
		{"label": _("Opening (kg)"), "fieldname": "opening_weight", "fieldtype": "Float", "width": 100},
		{"label": _("Balance (kg)"), "fieldname": "closing_weight", "fieldtype": "Float", "width": 100},
		{"label": _("Consumed (kg)"), "fieldname": "consumed_kg", "fieldtype": "Float", "width": 110},
	]
