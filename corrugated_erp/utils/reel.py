"""Keep Paper Reel balance weights in step with the stock ledger.

Every reel is an ERPNext Batch, so the stock ledger is the source of truth.
These helpers are called after any stock transaction that moves kraft paper.
"""

import frappe
from frappe.utils import flt

from corrugated_erp.utils.common import get_settings


def get_batch_balance(batch_no, item_code):
	"""Return (total_qty, warehouse_with_stock) for a batch across warehouses."""
	if not batch_no:
		return 0.0, None
	rows = []
	try:
		from erpnext.stock.doctype.batch.batch import get_batch_qty

		res = get_batch_qty(batch_no=batch_no, item_code=item_code)
		if isinstance(res, (int, float)):
			return flt(res), None
		rows = [(r.get("warehouse"), flt(r.get("qty"))) for r in (res or [])]
	except Exception:
		rows = frappe.db.sql(
			"""select warehouse, sum(actual_qty) from `tabStock Ledger Entry`
			where batch_no=%s and item_code=%s and is_cancelled=0 group by warehouse""",
			(batch_no, item_code),
		)
	total = sum(flt(q) for _, q in rows)
	warehouse = next((w for w, q in sorted(rows, key=lambda x: -flt(x[1])) if flt(q) > 0), None)
	return total, warehouse


def sync_reel(reel_name):
	reel = frappe.db.get_value(
		"Paper Reel",
		reel_name,
		["name", "batch_no", "paper_item", "status", "original_weight", "warehouse", "purchase_receipt", "opening_entry",
		 "reel_slitting"],
		as_dict=True,
	)
	if not reel or not reel.batch_no:
		return
	qty, warehouse = get_batch_balance(reel.batch_no, reel.paper_item)
	received = bool(reel.purchase_receipt or reel.opening_entry or reel.reel_slitting)
	status = reel.status
	if status in ("Damaged", "Returned", "Cancelled"):
		pass
	elif not received and qty <= 0:
		status = "Pending Receipt"
	elif qty <= flt(get_settings().min_reel_balance_kg):
		status = "Consumed"
	elif flt(reel.original_weight) and qty < flt(reel.original_weight) - 0.001:
		status = "Partially Used"
	else:
		status = "In Stock"
	values = {
		"current_weight": flt(qty, 3),
		"consumed_weight": flt(flt(reel.original_weight) - qty, 3) if received else 0,
		"status": status,
	}
	if warehouse:
		values["warehouse"] = warehouse
	frappe.db.set_value("Paper Reel", reel.name, values, update_modified=False)


def batches_in_row(row):
	"""Batch numbers moved by a stock transaction row (v14 batch_no or v15+ bundle)."""
	batches = set()
	if row.get("batch_no"):
		batches.add(row.batch_no)
	bundle = row.get("serial_and_batch_bundle")
	if bundle and frappe.db.exists("DocType", "Serial and Batch Entry"):
		batches.update(
			b for b in frappe.get_all("Serial and Batch Entry", filters={"parent": bundle}, pluck="batch_no") if b
		)
	return batches


def reels_for_doc(doc):
	batches = set()
	for row in doc.get("items") or []:
		if row.get("item_code") and frappe.get_cached_value("Item", row.item_code, "is_kraft_paper"):
			batches |= batches_in_row(row)
	if not batches:
		return []
	return frappe.get_all("Paper Reel", filters={"batch_no": ["in", list(batches)]}, pluck="name")


def sync_reels_for_doc(doc, method=None):
	for reel in reels_for_doc(doc):
		sync_reel(reel)
