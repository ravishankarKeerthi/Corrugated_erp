# Copyright (c) 2026, Syvasoft Business Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import flt

from corrugated_erp.utils import corrugation as calc
from corrugated_erp.utils.common import get_company, get_paper_rate, get_settings, validate_kraft_item


class ReelInward(Document):
	def onload(self):
		s = get_settings(self.company)
		if not self.warehouse and s.reel_warehouse:
			self.warehouse = s.reel_warehouse

	def validate(self):
		self.company = get_company(self.company)
		if not self.is_opening and not self.supplier:
			frappe.throw(_("Supplier is mandatory unless this is opening stock"))
		self.validate_reels()
		self.set_po_rates()
		self.calculate_totals()
		self.calculate_shortage()

	def validate_reels(self):
		seen = set()
		for d in self.reels:
			label = _("Row {0}: ").format(d.idx)
			validate_kraft_item(d.paper_item, label)
			if flt(d.deckle_mm) <= 0:
				frappe.throw(label + _("Enter the reel deckle"))
			d.deckle_inch = calc.mm_to_inch(d.deckle_mm)
			d.net_weight = flt(flt(d.gross_weight) - flt(d.core_weight), 3)
			if d.net_weight <= 0:
				frappe.throw(label + _("Net weight must be greater than zero"))
			d.reel_no = (d.reel_no or "").strip()
			if d.reel_no:
				if d.reel_no in seen:
					frappe.throw(label + _("Reel No {0} is repeated").format(d.reel_no))
				seen.add(d.reel_no)
				if self.reel_exists_elsewhere(d.reel_no):
					frappe.throw(label + _("Reel No {0} already exists").format(frappe.bold(d.reel_no)))

	def reel_exists_elsewhere(self, reel_no):
		reel = frappe.db.get_value("Paper Reel", reel_no, ["reel_inward", "status"], as_dict=True)
		if reel:
			# a reel from a cancelled inward can be re-used by its amendment
			return reel.status != "Cancelled" and reel.reel_inward != self.name
		return bool(frappe.db.exists("Batch", reel_no))

	def set_po_rates(self):
		po_items = {}
		if self.purchase_order and not self.is_opening:
			for row in frappe.get_all(
				"Purchase Order Item",
				filters={"parent": self.purchase_order},
				fields=["name", "item_code", "rate", "conversion_factor"],
			):
				po_items.setdefault(row.item_code, row)
		for d in self.reels:
			po = po_items.get(d.paper_item)
			d.purchase_order_item = po.name if po else None
			if not flt(d.rate):
				d.rate = flt(po.rate) / (flt(po.conversion_factor) or 1) if po else get_paper_rate(d.paper_item)
			d.amount = flt(flt(d.rate) * flt(d.net_weight), 2)

	def calculate_totals(self):
		self.total_reels = len(self.reels)
		self.total_gross_weight = flt(sum(flt(d.gross_weight) for d in self.reels), 3)
		self.total_net_weight = flt(sum(flt(d.net_weight) for d in self.reels), 3)
		self.total_amount = flt(sum(flt(d.amount) for d in self.reels), 2)

	def calculate_shortage(self):
		"""Mill / invoice weight against our weighbridge net weight."""
		total_invoice = total_short = short_value = 0.0
		for d in self.reels:
			d.shortage_kg = 0
			if flt(d.invoice_weight) > 0:
				total_invoice += flt(d.invoice_weight)
				d.shortage_kg = flt(max(flt(d.invoice_weight) - flt(d.net_weight), 0), 3)
				total_short += d.shortage_kg
				short_value += d.shortage_kg * flt(d.rate)
		self.total_invoice_weight = flt(total_invoice, 3)
		self.total_shortage_kg = flt(total_short, 3)
		tolerance = total_invoice * flt(get_settings(self.company).weight_tolerance_pct) / 100.0
		claimable = max(total_short - tolerance, 0) if not self.is_opening else 0
		self.claimable_shortage_kg = flt(claimable, 3)
		avg_rate = short_value / total_short if total_short else 0
		self.shortage_amount = flt(claimable * avg_rate, 2)

	# ---------------------------------------------------------------- submit
	def before_submit(self):
		series = get_settings(self.company).reel_naming_series or "RL-.YY.-.#####"
		for d in self.reels:
			if not d.reel_no:
				reel_no = make_autoname(series)
				while frappe.db.exists("Paper Reel", reel_no) or frappe.db.exists("Batch", reel_no):
					reel_no = make_autoname(series)
				d.reel_no = reel_no

	def on_submit(self):
		self.create_batches_and_reels()
		if self.is_opening:
			self.make_opening_entry()
		else:
			self.make_purchase_receipt()

	def create_batches_and_reels(self):
		for d in self.reels:
			batch_item = frappe.db.get_value("Batch", d.reel_no, "item")
			if batch_item and batch_item != d.paper_item:
				frappe.throw(
					_("Row {0}: reel no {1} was used earlier for {2}. Clear the reel no to auto-number.").format(
						d.idx, d.reel_no, batch_item
					)
				)
			if not batch_item:
				frappe.get_doc(
					{
						"doctype": "Batch",
						"batch_id": d.reel_no,
						"item": d.paper_item,
						"supplier": self.supplier,
						"manufacturing_date": self.posting_date,
						"description": _("Reel {0} {1} mm deckle").format(d.reel_no, flt(d.deckle_mm)),
					}
				).insert(ignore_permissions=True)
			if frappe.db.exists("Paper Reel", d.reel_no):
				reel = frappe.get_doc("Paper Reel", d.reel_no)
			else:
				reel = frappe.new_doc("Paper Reel")
				reel.reel_no = d.reel_no
			reel.update(
				{
					"paper_item": d.paper_item,
					"gsm": d.gsm,
					"bf": d.bf,
					"deckle_mm": d.deckle_mm,
					"original_weight": d.net_weight,
					"current_weight": 0,
					"warehouse": self.warehouse,
					"moisture_pct": d.moisture_pct,
					"supplier": self.supplier,
					"supplier_reel_no": d.supplier_reel_no,
					"received_date": self.posting_date,
					"reel_inward": self.name,
					"batch_no": d.reel_no,
					"status": "Pending Receipt",
				}
			)
			reel.flags.ignore_permissions = True
			reel.save()
			d.db_set("paper_reel", reel.name)

	def make_purchase_receipt(self):
		s = get_settings(self.company)
		pr = frappe.new_doc("Purchase Receipt")
		pr.update(
			{
				"supplier": self.supplier,
				"company": self.company,
				"posting_date": self.posting_date,
				"set_posting_time": 1,
				"supplier_delivery_note": self.supplier_invoice_no,
				"set_warehouse": self.warehouse,
				"reel_inward": self.name,
			}
		)
		for d in self.reels:
			row = {
				"item_code": d.paper_item,
				"qty": d.net_weight,
				"received_qty": d.net_weight,
				"rate": d.rate,
				"warehouse": self.warehouse,
				"batch_no": d.reel_no,
				"use_serial_batch_fields": 1,
			}
			if d.purchase_order_item:
				row.update({"purchase_order": self.purchase_order, "purchase_order_item": d.purchase_order_item})
			pr.append("items", row)
		pr.run_method("set_missing_values")
		pr.flags.ignore_permissions = True
		pr.insert()
		if s.auto_submit_purchase_receipt:
			pr.submit()
		self.db_set("purchase_receipt", pr.name)
		frappe.msgprint(
			_("Purchase Receipt {0} created{1}").format(
				frappe.get_desk_link("Purchase Receipt", pr.name),
				"" if s.auto_submit_purchase_receipt else _(" as draft - submit it to bring the reels into stock"),
			),
			indicator="green",
		)

	def make_opening_entry(self):
		se = frappe.new_doc("Stock Entry")
		se.update(
			{
				"stock_entry_type": "Material Receipt",
				"purpose": "Material Receipt",
				"company": self.company,
				"posting_date": self.posting_date,
				"set_posting_time": 1,
				"remarks": _("Opening reels from {0}").format(self.name),
			}
		)
		for d in self.reels:
			se.append(
				"items",
				{
					"item_code": d.paper_item,
					"qty": d.net_weight,
					"t_warehouse": self.warehouse,
					"basic_rate": d.rate,
					"batch_no": d.reel_no,
					"use_serial_batch_fields": 1,
				},
			)
		se.flags.ignore_permissions = True
		se.insert()
		se.submit()
		self.db_set("opening_entry", se.name)
		for d in self.reels:
			frappe.db.set_value("Paper Reel", d.reel_no, {"opening_entry": se.name, "status": "In Stock"}, update_modified=False)
		from corrugated_erp.utils.reel import sync_reel

		for d in self.reels:
			sync_reel(d.reel_no)

	# ---------------------------------------------------------------- cancel
	def on_cancel(self):
		self.ignore_linked_doctypes = ("Purchase Receipt", "Stock Entry", "Paper Reel", "Batch")
		if self.purchase_receipt:
			docstatus = frappe.db.get_value("Purchase Receipt", self.purchase_receipt, "docstatus")
			if docstatus == 1:
				frappe.throw(_("Cancel Purchase Receipt {0} first").format(self.purchase_receipt))
			if docstatus == 0:
				frappe.delete_doc("Purchase Receipt", self.purchase_receipt, ignore_permissions=True)
		if self.opening_entry:
			se = frappe.get_doc("Stock Entry", self.opening_entry)
			if se.docstatus == 1:
				se.flags.ignore_permissions = True
				se.cancel()
		for d in self.reels:
			if frappe.db.exists("Paper Reel", d.reel_no):
				frappe.db.set_value(
					"Paper Reel",
					d.reel_no,
					{"status": "Cancelled", "current_weight": 0, "purchase_receipt": None, "opening_entry": None},
					update_modified=False,
				)


@frappe.whitelist()
def make_shortage_debit_note(reel_inward):
	"""Draft debit note (Purchase Invoice return) for the claimable weight shortage."""
	from erpnext.accounts.doctype.purchase_invoice.purchase_invoice import make_debit_note

	ri = frappe.get_doc("Reel Inward", reel_inward)
	ri.check_permission("read")
	frappe.has_permission("Purchase Invoice", "create", throw=True)
	if ri.docstatus != 1 or not ri.purchase_receipt:
		frappe.throw(_("Submit the Reel Inward and its Purchase Receipt first"))
	if flt(ri.claimable_shortage_kg) <= 0:
		frappe.throw(_("There is no claimable shortage on {0}").format(ri.name))
	if ri.debit_note and frappe.db.get_value("Purchase Invoice", ri.debit_note, "docstatus") in (0, 1):
		return ri.debit_note
	invoice = frappe.db.sql(
		"""select distinct pi.name from `tabPurchase Invoice` pi
		join `tabPurchase Invoice Item` pii on pii.parent = pi.name
		where pii.purchase_receipt = %s and pi.docstatus = 1 and pi.is_return = 0
		order by pi.posting_date desc limit 1""",
		ri.purchase_receipt,
	)
	if not invoice:
		frappe.throw(
			_("Make and submit the Purchase Invoice for {0} (as per the supplier bill) before raising the shortage debit note").format(
				ri.purchase_receipt
			)
		)
	# shortage per paper item, scaled down to the claimable part
	ratio = flt(ri.claimable_shortage_kg) / flt(ri.total_shortage_kg) if flt(ri.total_shortage_kg) else 0
	short_by_item = {}
	for d in ri.reels:
		if flt(d.shortage_kg) > 0:
			row = short_by_item.setdefault(d.paper_item, {"qty": 0.0, "value": 0.0})
			row["qty"] += flt(d.shortage_kg) * ratio
			row["value"] += flt(d.shortage_kg) * ratio * flt(d.rate)
	dn = make_debit_note(invoice[0][0])
	rows = []
	for row in dn.items:
		short = short_by_item.pop(row.item_code, None)
		if not short or short["qty"] <= 0:
			continue
		row.qty = -flt(short["qty"], 3)
		row.rate = flt(short["value"] / short["qty"], 2)
		if row.meta.has_field("received_qty"):
			row.received_qty = 0
		rows.append(row)
	if not rows:
		frappe.throw(_("The paper items of {0} were not found on the Purchase Invoice").format(ri.name))
	dn.set("items", rows)
	dn.update_stock = 0
	dn.remarks = _("Weight shortage claim for {0}: {1} kg").format(ri.name, ri.claimable_shortage_kg)
	dn.run_method("calculate_taxes_and_totals")
	dn.insert()
	ri.db_set("debit_note", dn.name)
	return dn.name
