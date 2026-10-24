# Copyright (c) 2026, Syvasoft Business Solutions and contributors
# For license information, please see license.txt

from frappe.model.document import Document
from frappe.utils import cint, flt


class BoxTooling(Document):
	def validate(self):
		life = cint(self.impressions_life)
		self.utilisation_pct = flt(cint(self.impressions_used) / life * 100, 2) if life else 0
