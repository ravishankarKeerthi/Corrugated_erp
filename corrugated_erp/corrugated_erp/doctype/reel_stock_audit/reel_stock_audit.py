# Copyright (c) 2026, Syvasoft Business Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt

from corrugated_erp.utils.common import ACTIVE_REEL_STATUSES


class ReelStockAudit(Document):
	def validate(self):
		self.compare()

	def compare(self):
		in_system = {
			r.name: r
			for r in frappe.get_all(
				"Paper Reel",
				filters={"warehouse": self.warehouse, "status": ["in", ACTIVE_REEL_STATUSES]},
				fields=["name", "paper_item", "current_weight", "location"],
			)
		}
		scanned = set()
		found = not_in_system = 0
		weight_diff = 0.0
		for d in self.scans:
			d.reel_no = (d.reel_no or "").strip()
			reel = frappe.db.get_value(
				"Paper Reel", d.reel_no, ["name", "paper_item", "status", "warehouse", "current_weight"], as_dict=True
			)
			if not reel:
				d.paper_reel = None
				d.audit_result = "Not In System"
				not_in_system += 1
				continue
			scanned.add(reel.name)
			d.paper_reel = reel.name
			d.paper_item = reel.paper_item
			d.system_status = reel.status
			d.system_warehouse = reel.warehouse
			d.system_weight = reel.current_weight
			d.weight_difference = flt(flt(d.physical_weight) - flt(reel.current_weight), 3) if flt(d.physical_weight) else 0
			weight_diff += d.weight_difference
			if reel.status not in ACTIVE_REEL_STATUSES:
				d.audit_result = "Not In Stock"
			elif reel.warehouse != self.warehouse:
				d.audit_result = "Wrong Location"
			else:
				d.audit_result = "Found"
				found += 1

		self.set("missing", [])
		for name, r in in_system.items():
			if name not in scanned:
				self.append(
					"missing",
					{"paper_reel": name, "paper_item": r.paper_item, "system_weight": r.current_weight, "location": r.location},
				)
		self.system_reel_count = len(in_system)
		self.scanned_count = len(self.scans)
		self.found_count = found
		self.missing_count = len(self.missing)
		self.not_in_system_count = not_in_system
		self.weight_difference_kg = flt(weight_diff, 3)

	def on_submit(self):
		for d in self.scans:
			if d.paper_reel:
				frappe.db.set_value("Paper Reel", d.paper_reel, "last_audit_date", self.audit_date, update_modified=False)
