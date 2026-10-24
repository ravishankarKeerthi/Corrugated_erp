# Copyright (c) 2026, Syvasoft Business Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = frappe._dict(filters or {})
	cond = ["ri.docstatus = 1", "ri.is_opening = 0", "ri.total_shortage_kg > 0",
		"ri.posting_date between %(from_date)s and %(to_date)s"]
	if filters.get("supplier"):
		cond.append("ri.supplier = %(supplier)s")
	if filters.get("company"):
		cond.append("ri.company = %(company)s")
	if filters.get("pending_only"):
		cond.append("ri.claimable_shortage_kg > 0 and (ri.debit_note is null or ri.debit_note = '')")
	rows = frappe.db.sql(
		"""select ri.name reel_inward, ri.posting_date, ri.supplier, ri.supplier_invoice_no, ri.total_reels,
			ri.total_invoice_weight, ri.total_net_weight, ri.total_shortage_kg, ri.claimable_shortage_kg,
			ri.shortage_amount, ri.debit_note
		from `tabReel Inward` ri where {0} order by ri.posting_date desc""".format(" and ".join(cond)),
		filters,
		as_dict=True,
	)
	for r in rows:
		r.shortage_pct = flt(flt(r.total_shortage_kg) / flt(r.total_invoice_weight) * 100, 2) if flt(r.total_invoice_weight) else 0
		if r.debit_note:
			ds = frappe.db.get_value("Purchase Invoice", r.debit_note, "docstatus")
			r.claim_status = {0: _("Debit Note Draft"), 1: _("Claimed"), 2: _("Debit Note Cancelled")}.get(ds, "")
		else:
			r.claim_status = _("To Claim") if flt(r.claimable_shortage_kg) > 0 else _("Within Tolerance")
	columns = [
		{"label": _("Reel Inward"), "fieldname": "reel_inward", "fieldtype": "Link", "options": "Reel Inward", "width": 130},
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 95},
		{"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 160},
		{"label": _("Invoice No"), "fieldname": "supplier_invoice_no", "fieldtype": "Data", "width": 110},
		{"label": _("Reels"), "fieldname": "total_reels", "fieldtype": "Int", "width": 65},
		{"label": _("Invoice Wt (kg)"), "fieldname": "total_invoice_weight", "fieldtype": "Float", "width": 115},
		{"label": _("Actual Wt (kg)"), "fieldname": "total_net_weight", "fieldtype": "Float", "width": 110},
		{"label": _("Short (kg)"), "fieldname": "total_shortage_kg", "fieldtype": "Float", "width": 90},
		{"label": _("Short %"), "fieldname": "shortage_pct", "fieldtype": "Percent", "width": 80},
		{"label": _("Claimable (kg)"), "fieldname": "claimable_shortage_kg", "fieldtype": "Float", "width": 110},
		{"label": _("Claim Amount"), "fieldname": "shortage_amount", "fieldtype": "Currency", "width": 115},
		{"label": _("Claim Status"), "fieldname": "claim_status", "fieldtype": "Data", "width": 125},
		{"label": _("Debit Note"), "fieldname": "debit_note", "fieldtype": "Link", "options": "Purchase Invoice", "width": 130},
	]
	return columns, rows
