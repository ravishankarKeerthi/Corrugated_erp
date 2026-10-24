# Copyright (c) 2026, Syvasoft Business Solutions and contributors
# For license information, please see license.txt

"""Cut (slit / rewind) one paper reel into narrower reels.

Stock: one Repack Stock Entry - the parent reel's batch goes out, each new reel comes in
as its own batch of the same paper item, and the edge trim goes to scrap stock at zero
value (its cost stays in the new reels, so the paper cost per kg is unchanged overall).
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from corrugated_erp.utils import corrugation as calc
from corrugated_erp.utils.common import ACTIVE_REEL_STATUSES, get_company, get_settings
from corrugated_erp.utils.reel import sync_reel


class ReelSlitting(Document):
	def validate(self):
		self.company = get_company(self.company)
		self.set_parent_details()
		self.calculate()

	def set_parent_details(self):
		reel = frappe.db.get_value(
			"Paper Reel",
			self.parent_reel,
			["status", "paper_item", "batch_no", "warehouse", "deckle_mm", "current_weight", "quality_status"],
			as_dict=True,
		)
		if not reel:
			frappe.throw(_("Reel {0} not found").format(self.parent_reel))
		if self.docstatus == 0:
			sync_reel(self.parent_reel)
			reel.current_weight = frappe.db.get_value("Paper Reel", self.parent_reel, "current_weight")
			if reel.status not in ACTIVE_REEL_STATUSES:
				frappe.throw(_("Reel {0} is {1} and cannot be cut").format(self.parent_reel, reel.status))
			if reel.quality_status == "Fail":
				frappe.throw(_("Reel {0} failed the incoming quality test").format(self.parent_reel))
			self.parent_weight_kg = flt(reel.current_weight)
		self.paper_item = reel.paper_item
		self.batch_no = reel.batch_no
		self.warehouse = reel.warehouse
		self.parent_deckle_mm = reel.deckle_mm
		if not flt(self.slit_weight_kg):
			self.slit_weight_kg = self.parent_weight_kg

	def calculate(self):
		if flt(self.slit_weight_kg) <= 0 or flt(self.slit_weight_kg) > flt(self.parent_weight_kg) + 0.001:
			frappe.throw(_("Weight being cut must be between 0 and the reel balance {0} kg").format(self.parent_weight_kg))
		if not self.outputs:
			frappe.throw(_("Enter at least one new reel"))
		try:
			res = calc.split_reel(self.slit_weight_kg, self.parent_deckle_mm, [d.deckle_mm for d in self.outputs])
		except ValueError as e:
			frappe.throw(str(e))
		for d, w in zip(self.outputs, res["child_weights"]):
			d.deckle_inch = calc.mm_to_inch(d.deckle_mm)
			if not flt(d.weight_kg):
				d.weight_kg = w
			d.reel_no = (d.reel_no or "").strip()
		total = flt(sum(flt(d.weight_kg) for d in self.outputs), 3)
		if total > flt(self.slit_weight_kg) + 0.001:
			frappe.throw(_("New reels ({0} kg) weigh more than the weight being cut ({1} kg)").format(total, self.slit_weight_kg))
		self.used_deckle_mm = res["used_deckle_mm"]
		self.trim_deckle_mm = res["trim_deckle_mm"]
		self.total_output_kg = total
		self.trim_weight_kg = flt(flt(self.slit_weight_kg) - total, 3)
		seen = set()
		for d in self.outputs:
			if d.reel_no:
				if d.reel_no in seen:
					frappe.throw(_("Row {0}: reel no {1} is repeated").format(d.idx, d.reel_no))
				seen.add(d.reel_no)
				if frappe.db.exists("Paper Reel", d.reel_no) and frappe.db.get_value("Paper Reel", d.reel_no, "reel_slitting") != self.name:
					frappe.throw(_("Row {0}: reel no {1} already exists").format(d.idx, d.reel_no))

	def before_submit(self):
		used = {d.reel_no for d in self.outputs if d.reel_no}
		n = 0
		for d in self.outputs:
			if d.reel_no:
				continue
			while True:
				n += 1
				candidate = "{0}/{1}".format(self.parent_reel, n)
				if candidate not in used and not frappe.db.exists("Paper Reel", candidate) and not frappe.db.exists("Batch", candidate):
					break
			d.reel_no = candidate
			used.add(candidate)

	def on_submit(self):
		parent = frappe.db.get_value("Paper Reel", self.parent_reel, ["supplier", "gsm", "bf", "moisture_pct", "supplier_reel_no", "quality_status"], as_dict=True)
		for d in self.outputs:
			if not frappe.db.exists("Batch", d.reel_no):
				frappe.get_doc(
					{
						"doctype": "Batch",
						"batch_id": d.reel_no,
						"item": self.paper_item,
						"supplier": parent.supplier,
						"manufacturing_date": self.posting_date,
						"description": _("Cut from reel {0}, {1} mm deckle").format(self.parent_reel, flt(d.deckle_mm)),
					}
				).insert(ignore_permissions=True)
			reel = frappe.get_doc("Paper Reel", d.reel_no) if frappe.db.exists("Paper Reel", d.reel_no) else frappe.new_doc("Paper Reel")
			reel.update(
				{
					"reel_no": d.reel_no,
					"paper_item": self.paper_item,
					"gsm": parent.gsm,
					"bf": parent.bf,
					"deckle_mm": d.deckle_mm,
					"original_weight": d.weight_kg,
					"current_weight": 0,
					"warehouse": self.warehouse,
					"location": d.location,
					"moisture_pct": parent.moisture_pct,
					"supplier": parent.supplier,
					"supplier_reel_no": parent.supplier_reel_no,
					"received_date": self.posting_date,
					"parent_reel": self.parent_reel,
					"reel_slitting": self.name,
					"quality_status": parent.quality_status or "Pending",
					"batch_no": d.reel_no,
					"status": "In Stock",
				}
			)
			reel.flags.ignore_permissions = True
			reel.save()
			d.db_set("paper_reel", reel.name)
		self.make_stock_entry()
		for d in self.outputs:
			sync_reel(d.reel_no)
		sync_reel(self.parent_reel)

	def make_stock_entry(self):
		s = get_settings(self.company)
		se = frappe.new_doc("Stock Entry")
		se.update(
			{
				"stock_entry_type": "Repack",
				"purpose": "Repack",
				"company": self.company,
				"posting_date": self.posting_date,
				"set_posting_time": 1,
				"remarks": _("Reel {0} cut into {1} reels ({2})").format(self.parent_reel, len(self.outputs), self.name),
			}
		)
		uom = frappe.db.get_value("Item", self.paper_item, "stock_uom")
		common = {"item_code": self.paper_item, "uom": uom, "stock_uom": uom, "conversion_factor": 1, "use_serial_batch_fields": 1}
		se.append("items", dict(common, qty=flt(self.slit_weight_kg, 3), s_warehouse=self.warehouse, batch_no=self.batch_no))
		for d in self.outputs:
			se.append("items", dict(common, qty=flt(d.weight_kg, 3), t_warehouse=self.warehouse, batch_no=d.reel_no, is_finished_item=1))
		if flt(self.trim_weight_kg) > 0:
			if s.scrap_item and s.scrap_warehouse:
				se.append(
					"items",
					{
						"item_code": s.scrap_item,
						"qty": flt(self.trim_weight_kg, 3),
						"t_warehouse": s.scrap_warehouse,
						"is_scrap_item": 1,
						"allow_zero_valuation_rate": 1,
					},
				)
		se.flags.ignore_permissions = True
		se.insert()
		se.submit()
		self.db_set("stock_entry", se.name)

	def on_cancel(self):
		self.ignore_linked_doctypes = ("Stock Entry", "Paper Reel", "Batch", "Stock Ledger Entry")
		for d in self.outputs:
			if d.reel_no and frappe.db.exists("Paper Reel", d.reel_no):
				used = frappe.db.sql(
					"""select pe.name from `tabProduction Entry Reel` per join `tabProduction Entry` pe on pe.name = per.parent
					where per.paper_reel = %s and pe.docstatus = 1 limit 1""",
					d.reel_no,
				)
				if used:
					frappe.throw(_("Reel {0} is already used in {1}. Cancel that first.").format(d.reel_no, used[0][0]))
		if self.stock_entry and frappe.db.get_value("Stock Entry", self.stock_entry, "docstatus") == 1:
			se = frappe.get_doc("Stock Entry", self.stock_entry)
			se.flags.ignore_permissions = True
			se.cancel()
		for d in self.outputs:
			if d.reel_no and frappe.db.exists("Paper Reel", d.reel_no):
				frappe.db.set_value("Paper Reel", d.reel_no, {"status": "Cancelled", "current_weight": 0}, update_modified=False)
		sync_reel(self.parent_reel)


@frappe.whitelist()
def split_weights(parent_weight_kg, parent_deckle_mm, deckles):
	"""Proportional weights for the form."""
	deckles = frappe.parse_json(deckles) if isinstance(deckles, str) else deckles
	try:
		return calc.split_reel(parent_weight_kg, parent_deckle_mm, deckles)
	except ValueError as e:
		frappe.throw(str(e))
