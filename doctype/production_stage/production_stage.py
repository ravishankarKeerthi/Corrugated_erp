# Copyright (c) 2026, Syvasoft Business Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class ProductionStage(Document):
	def validate(self):
		if self.is_final_stage and self.is_active:
			other = frappe.db.get_value(
				"Production Stage", {"is_final_stage": 1, "is_active": 1, "name": ["!=", self.name]}, "name"
			)
			if other:
				frappe.throw(_("{0} is already the final stage. Only one active final stage is allowed.").format(other))
		if self.consumes_reels and self.is_final_stage:
			frappe.throw(_("A stage cannot both consume reels and be the final stage"))
