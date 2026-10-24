# Copyright (c) 2026, Syvasoft Business Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import date_diff, flt, nowdate


def execute(filters=None):
	filters = frappe._dict(filters or {})
	conditions = {}
	statuses = filters.get("status") or ["In Stock", "Partially Used"]
	conditions["status"] = ["in", statuses]
	for field in ("warehouse", "paper_item", "supplier"):
		if filters.get(field):
			conditions[field] = filters.get(field)
	if filters.get("gsm"):
		conditions["gsm"] = flt(filters.gsm)
	if filters.get("deckle_from") or filters.get("deckle_to"):
		conditions["deckle_mm"] = ["between", [flt(filters.deckle_from), flt(filters.deckle_to) or 99999]]

	reels = frappe.get_all(
		"Paper Reel",
		filters=conditions,
		fields=[
			"name",
			"paper_item",
			"item_name",
			"bf",
			"gsm",
			"shade",
			"deckle_mm",
			"deckle_inch",
			"supplier",
			"received_date",
			"original_weight",
			"current_weight",
			"consumed_weight",
			"warehouse",
			"location",
			"status",
			"quality_status",
		],
		order_by="paper_item, deckle_mm, received_date",
	)
	today = nowdate()
	data = []
	for r in reels:
		r["age_days"] = date_diff(today, r.received_date) if r.received_date else None
		if filters.get("min_age_days") and (r["age_days"] or 0) < int(filters.min_age_days):
			continue
		data.append(r)
	return get_columns(), data, None, get_chart(data), get_summary(data)


def get_columns():
	return [
		{"label": _("Reel"), "fieldname": "name", "fieldtype": "Link", "options": "Paper Reel", "width": 130},
		{"label": _("Paper Item"), "fieldname": "paper_item", "fieldtype": "Link", "options": "Item", "width": 150},
		{"label": _("BF"), "fieldname": "bf", "fieldtype": "Float", "width": 60},
		{"label": _("GSM"), "fieldname": "gsm", "fieldtype": "Float", "width": 70},
		{"label": _("Shade"), "fieldname": "shade", "fieldtype": "Data", "width": 90},
		{"label": _("Deckle (mm)"), "fieldname": "deckle_mm", "fieldtype": "Float", "width": 100},
		{"label": _("Deckle (in)"), "fieldname": "deckle_inch", "fieldtype": "Float", "width": 90},
		{"label": _("Balance (kg)"), "fieldname": "current_weight", "fieldtype": "Float", "width": 110},
		{"label": _("Received (kg)"), "fieldname": "original_weight", "fieldtype": "Float", "width": 110},
		{"label": _("Age (days)"), "fieldname": "age_days", "fieldtype": "Int", "width": 90},
		{"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 140},
		{"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 140},
		{"label": _("Bay / Rack"), "fieldname": "location", "fieldtype": "Data", "width": 90},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 110},
		{"label": _("Quality"), "fieldname": "quality_status", "fieldtype": "Data", "width": 80},
	]


def get_chart(data):
	by_gsm = {}
	for r in data:
		key = "{0} GSM".format(flt(r.gsm, 0))
		by_gsm[key] = by_gsm.get(key, 0) + flt(r.current_weight)
	if not by_gsm:
		return None
	labels = sorted(by_gsm, key=lambda k: flt(k.split()[0]))
	return {
		"data": {"labels": labels, "datasets": [{"name": _("Balance kg"), "values": [flt(by_gsm[k], 0) for k in labels]}]},
		"type": "bar",
	}


def get_summary(data):
	total = sum(flt(r.current_weight) for r in data)
	old = [r for r in data if (r.get("age_days") or 0) > 90]
	return [
		{"label": _("Reels"), "value": len(data), "datatype": "Int", "indicator": "Blue"},
		{"label": _("Balance (kg)"), "value": flt(total, 0), "datatype": "Float", "indicator": "Green"},
		{"label": _("Reels older than 90 days"), "value": len(old), "datatype": "Int", "indicator": "Orange" if old else "Green"},
	]
