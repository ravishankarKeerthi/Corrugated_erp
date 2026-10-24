# Copyright (c) 2026, Syvasoft Business Solutions and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt

from corrugated_erp.utils import corrugation as calc
from corrugated_erp.utils.common import get_settings, standard_deckles


class DecklePlan(Document):
	def validate(self):
		if not flt(self.min_trim_mm):
			self.min_trim_mm = get_settings().min_deckle_trim_mm
		self.calculate()
		if self.status == "Planned":
			if not flt(self.deckle_mm):
				frappe.throw(_("Select the reel deckle before marking the plan as Planned"))
			if flt(self.total_used_width_mm) + flt(self.min_trim_mm) > flt(self.deckle_mm):
				frappe.throw(
					_("Used width {0} mm + minimum trim {1} mm does not fit on a {2} mm deckle").format(
						self.total_used_width_mm, self.min_trim_mm, self.deckle_mm
					)
				)

	def calculate(self):
		used = 0.0
		running = 0.0
		seen = set()
		for d in self.items:
			if d.work_order in seen:
				frappe.throw(_("Row {0}: Work Order {1} is repeated").format(d.idx, d.work_order))
			seen.add(d.work_order)
			if flt(d.sheet_width_mm) <= 0:
				frappe.throw(_("Row {0}: sheet width is missing - link a Box Specification to the Work Order").format(d.idx))
			d.outs = max(1, cint(d.outs))
			d.used_width_mm = flt(flt(d.sheet_width_mm) * d.outs, 1)
			ups = cint(frappe.db.get_value("Box Specification", d.box_spec, "ups_per_sheet")) if d.box_spec else 1
			d.cuts_required = calc.cuts_required(d.qty, d.outs, ups or 1)
			d.running_metres = flt(d.cuts_required * flt(d.sheet_length_mm) / 1000.0, 1)
			used += d.used_width_mm
			running = max(running, d.running_metres)
		self.total_used_width_mm = flt(used, 1)
		self.total_running_metres = flt(running, 1)
		self.deckle_inch = calc.mm_to_inch(self.deckle_mm)
		if flt(self.deckle_mm):
			self.trim_mm = flt(flt(self.deckle_mm) - used, 1)
			self.trim_pct = flt(self.trim_mm / flt(self.deckle_mm) * 100, 2)
		else:
			self.trim_mm = self.trim_pct = 0

	def on_update(self):
		if self.status in ("Planned", "Completed"):
			for d in self.items:
				frappe.db.set_value(
					"Work Order", d.work_order, {"deckle_mm": self.deckle_mm, "outs": d.outs, "deckle_plan": self.name}
				)


@frappe.whitelist()
def suggest(doc):
	if isinstance(doc, str):
		doc = json.loads(doc)
	items = doc.get("items") or []
	s = get_settings()
	min_trim = flt(doc.get("min_trim_mm")) or flt(s.min_deckle_trim_mm)
	rows = [{"width_mm": flt(d.get("sheet_width_mm")), "outs": 0 if len(items) == 1 else cint(d.get("outs")) or 1} for d in items]
	return calc.deckle_options(rows, standard_deckles(s), min_trim)[:10]
