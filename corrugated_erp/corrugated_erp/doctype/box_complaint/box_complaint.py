# Copyright (c) 2026, Syvasoft Business Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today


class BoxComplaint(Document):
	def validate(self):
		self.fill_links()
		if self.status == "Closed":
			if not self.resolution:
				frappe.throw(_("Select the resolution before closing the complaint"))
			if self.resolution != "Rejected - Not Valid" and not self.corrective_action:
				frappe.throw(_("Enter the corrective action before closing the complaint"))
			if not self.closed_on:
				self.closed_on = today()
		else:
			self.closed_on = None
		if self.resolution == "Credit Note" and self.credit_note:
			is_return = frappe.db.get_value("Sales Invoice", self.credit_note, "is_return")
			if not is_return:
				frappe.throw(_("{0} is not a credit note (return invoice)").format(self.credit_note))

	def fill_links(self):
		"""Fill box spec and work order from the delivery note where possible."""
		if self.delivery_note and not (self.box_spec and self.work_order):
			row = frappe.db.get_value(
				"Delivery Note Item",
				{"parent": self.delivery_note, "box_spec": ["is", "set"]},
				["box_spec", "against_sales_order"],
				as_dict=True,
			)
			if row:
				self.box_spec = self.box_spec or row.box_spec
				if not self.work_order and row.against_sales_order:
					self.work_order = frappe.db.get_value(
						"Work Order",
						{"sales_order": row.against_sales_order, "box_spec": row.box_spec, "docstatus": 1},
						"name",
						order_by="creation desc",
					)
		if self.work_order and not self.box_spec:
			self.box_spec = frappe.db.get_value("Work Order", self.work_order, "box_spec")


@frappe.whitelist()
def get_trace(work_order):
	"""Production entries and reels behind a work order, for complaint investigation."""
	frappe.has_permission("Production Entry", "read", throw=True)
	rows = frappe.db.sql(
		"""select pe.name production_entry, pe.posting_date, pe.production_stage,
			per.paper_reel, per.paper_item, pr.supplier, pr.quality_status
		from `tabProduction Entry` pe
		left join `tabProduction Entry Reel` per on per.parent = pe.name
		left join `tabPaper Reel` pr on pr.name = per.paper_reel
		where pe.work_order = %s and pe.docstatus = 1
		order by pe.posting_date, pe.name""",
		work_order,
		as_dict=True,
	)
	return rows
