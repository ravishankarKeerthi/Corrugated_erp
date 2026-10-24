# Copyright (c) 2026, Syvasoft Business Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import date_diff, flt, nowdate

from corrugated_erp.utils import corrugation as calc
from corrugated_erp.utils.reel import sync_reel


class PaperReel(Document):
	def validate(self):
		self.deckle_inch = calc.mm_to_inch(self.deckle_mm)
		if self.is_new() and not (self.reel_inward or self.reel_slitting) and not frappe.flags.in_import:
			frappe.throw(_("Paper Reels are created from Reel Inward (use 'Opening Stock' on Reel Inward for existing reels)"))
		if self.purchase_receipt or self.opening_entry or self.reel_slitting:
			self.consumed_weight = flt(flt(self.original_weight) - flt(self.current_weight), 3)

	def onload(self):
		if self.received_date:
			self.set_onload("age_days", date_diff(nowdate(), self.received_date))


@frappe.whitelist()
def make_purchase_return(reel):
	"""Draft Purchase Return for one rejected / damaged reel, against its Purchase Receipt."""
	from erpnext.stock.doctype.purchase_receipt.purchase_receipt import make_purchase_return as erpnext_return

	doc = frappe.get_doc("Paper Reel", reel)
	doc.check_permission("write")
	if not doc.purchase_receipt:
		frappe.throw(_("Reel {0} has no Purchase Receipt (opening or cut reel) - it cannot be returned to a supplier").format(reel))
	sync_reel(reel)
	balance = flt(frappe.db.get_value("Paper Reel", reel, "current_weight"))
	if balance <= 0:
		frappe.throw(_("Reel {0} has no balance to return").format(reel))
	ret = erpnext_return(doc.purchase_receipt)
	keep = []
	for row in ret.items:
		if row.item_code == doc.paper_item and (row.get("batch_no") == doc.batch_no or not keep):
			keep = [row]
			if row.get("batch_no") == doc.batch_no:
				break
	if not keep:
		frappe.throw(_("Reel {0} was not found on Purchase Receipt {1}").format(reel, doc.purchase_receipt))
	row = keep[0]
	row.qty = -balance
	row.received_qty = -balance
	row.stock_qty = -balance
	row.batch_no = doc.batch_no
	row.warehouse = doc.warehouse or row.warehouse
	if row.meta.has_field("serial_and_batch_bundle"):
		row.serial_and_batch_bundle = None
	if row.meta.has_field("use_serial_batch_fields"):
		row.use_serial_batch_fields = 1
	ret.set("items", [row])
	ret.remarks = _("Return of reel {0}").format(reel)
	ret.insert()
	return ret.name


@frappe.whitelist()
def refresh_balance(reel):
	frappe.get_doc("Paper Reel", reel).check_permission("read")
	sync_reel(reel)
	return frappe.db.get_value("Paper Reel", reel, ["current_weight", "status", "warehouse"], as_dict=True)
