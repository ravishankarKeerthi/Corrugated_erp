# Copyright (c) 2026, Syvasoft Business Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from corrugated_erp.utils import corrugation as calc


class CorrugationSettings(Document):
	def validate(self):
		rows = []
		for d in self.standard_deckles:
			if not flt(d.deckle_mm) and flt(d.deckle_inch):
				d.deckle_mm = calc.inch_to_mm(d.deckle_inch)
			if not flt(d.deckle_mm):
				frappe.throw(_("Row {0}: enter the deckle in mm or inch").format(d.idx))
			d.deckle_inch = calc.mm_to_inch(d.deckle_mm)
			rows.append(d)
		rows.sort(key=lambda d: flt(d.deckle_mm))
		for i, d in enumerate(rows, start=1):
			d.idx = i
		if flt(self.process_waste_pct) < 0 or flt(self.process_waste_pct) > 50:
			frappe.throw(_("Process waste % should be between 0 and 50"))
