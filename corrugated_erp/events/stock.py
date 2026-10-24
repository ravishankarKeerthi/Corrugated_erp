"""Doc events on ERPNext stock documents."""

import frappe
from frappe import _
from frappe.utils import cint, flt

from corrugated_erp.utils import corrugation as calc
from corrugated_erp.utils.reel import reels_for_doc, sync_reel


def purchase_receipt_on_submit(doc, method=None):
	"""Reels arrive in stock when their Purchase Receipt is submitted; a return marks them Returned."""
	if doc.get("is_return"):
		for reel in reels_for_doc(doc):
			sync_reel(reel)
			if flt(frappe.db.get_value("Paper Reel", reel, "current_weight")) <= 0.001:
				frappe.db.set_value("Paper Reel", reel, "status", "Returned", update_modified=False)
		return
	for reel in reels_for_doc(doc):
		values = {"purchase_receipt": doc.name, "received_date": doc.posting_date}
		if frappe.db.get_value("Paper Reel", reel, "status") in ("Pending Receipt", "Cancelled"):
			values["status"] = "In Stock"
		frappe.db.set_value("Paper Reel", reel, values, update_modified=False)
		sync_reel(reel)


def purchase_receipt_on_cancel(doc, method=None):
	if doc.get("is_return"):
		for reel in reels_for_doc(doc):
			if frappe.db.get_value("Paper Reel", reel, "status") == "Returned":
				frappe.db.set_value("Paper Reel", reel, "status", "In Stock", update_modified=False)
			sync_reel(reel)
		return
	for reel in reels_for_doc(doc):
		frappe.db.set_value(
			"Paper Reel", reel, {"purchase_receipt": None, "status": "Pending Receipt"}, update_modified=False
		)
		sync_reel(reel)


def stock_entry_on_submit_or_cancel(doc, method=None):
	"""Any stock entry that moves kraft paper batches refreshes those reels."""
	for reel in reels_for_doc(doc):
		sync_reel(reel)


def stock_reco_on_submit_or_cancel(doc, method=None):
	for reel in reels_for_doc(doc):
		sync_reel(reel)


def work_order_validate(doc, method=None):
	"""Carry box specification sheet sizes onto the Work Order."""
	if not doc.get("box_spec") and doc.production_item:
		doc.box_spec = frappe.db.get_value("Item", doc.production_item, "box_spec")
	if doc.get("box_spec"):
		spec = frappe.db.get_value(
			"Box Specification",
			doc.box_spec,
			["sheet_length_mm", "sheet_width_mm", "suggested_deckle_mm", "outs_on_reel", "ups_per_sheet"],
			as_dict=True,
		)
		if spec:
			doc.sheet_length_mm = spec.sheet_length_mm
			doc.sheet_width_mm = spec.sheet_width_mm
			doc.ups = cint(spec.ups_per_sheet) or 1
			doc.sheets_required = calc.sheets_required(doc.qty, doc.ups)
			if not flt(doc.get("deckle_mm")):
				doc.deckle_mm = spec.suggested_deckle_mm
			if not doc.get("outs"):
				doc.outs = spec.outs_on_reel


def delivery_note_validate(doc, method=None):
	"""Bundle count for each box line and the whole challan."""
	total = 0.0
	for row in doc.get("items") or []:
		per_bundle = flt(row.get("boxes_per_bundle"))
		if not per_bundle and row.get("box_spec"):
			per_bundle = flt(frappe.db.get_value("Box Specification", row.box_spec, "boxes_per_bundle"))
			row.boxes_per_bundle = per_bundle
		row.no_of_bundles = flt(flt(row.qty) / per_bundle, 2) if per_bundle else 0
		total += row.no_of_bundles
	doc.total_bundles = flt(total, 2)


def item_validate(doc, method=None):
	if doc.get("is_kraft_paper"):
		if not doc.has_batch_no:
			doc.has_batch_no = 1
		if not doc.is_stock_item:
			frappe.throw(_("Kraft paper items must be stock items"))
		if not flt(doc.get("paper_gsm")):
			frappe.throw(_("Enter Paper GSM for kraft paper item {0}").format(doc.name or doc.item_code))
