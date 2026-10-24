# Copyright (c) 2026, Syvasoft Business Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from corrugated_erp.utils import corrugation as calc
from corrugated_erp.utils.common import get_paper_rate, get_settings, upsert_item_price


class PaperPriceRevision(Document):
	def onload(self):
		if not self.price_list:
			self.price_list = get_settings().paper_price_list

	def validate(self):
		seen = set()
		for d in self.items:
			if d.paper_item in seen:
				frappe.throw(_("Row {0}: {1} is entered twice").format(d.idx, d.paper_item))
			seen.add(d.paper_item)
			if self.docstatus == 0:
				d.current_rate = get_paper_rate(d.paper_item, self.price_list)
			d.change_pct = flt((flt(d.new_rate) / flt(d.current_rate) - 1) * 100, 2) if flt(d.current_rate) else 0
		if self.docstatus == 0:
			self.calculate_impact()

	def calculate_impact(self):
		new_rates = {d.paper_item: flt(d.new_rate) for d in self.items if flt(d.new_rate)}
		self.set("impacts", [])
		if not new_rates:
			return
		costings = frappe.db.sql(
			"""select distinct spec.name as box_spec, spec.box_name, spec.customer, spec.latest_costing
			from `tabBox Specification` spec
			join `tabBox Costing Paper` p on p.parent = spec.latest_costing and p.parenttype = 'Box Costing'
			where spec.status = 'Active' and ifnull(spec.latest_costing, '') != '' and p.paper_item in %(items)s""",
			{"items": tuple(new_rates)},
			as_dict=True,
		)
		changes = []
		for row in costings:
			costing = frappe.get_doc("Box Costing", row.latest_costing)
			new = calc.compute_cost(costing.cost_inputs(new_rates))
			old_cost = flt(costing.total_cost_per_box)
			old_price = flt(costing.final_price_per_box)
			markup = (old_price / old_cost) if old_cost else 1 + flt(costing.margin_pct) / 100.0
			change = (new["total_cost_per_box"] / old_cost - 1) * 100 if old_cost else 0
			changes.append(change)
			self.append(
				"impacts",
				{
					"box_spec": row.box_spec,
					"box_name": row.box_name,
					"customer": row.customer,
					"box_costing": costing.name,
					"old_cost_per_box": old_cost,
					"new_cost_per_box": new["total_cost_per_box"],
					"old_price_per_box": old_price,
					"suggested_price_per_box": flt(new["total_cost_per_box"] * markup, 4),
					"cost_change_pct": flt(change, 2),
				},
			)
		self.specs_affected = len(self.impacts)
		self.avg_cost_change_pct = flt(sum(changes) / len(changes), 2) if changes else 0

	def before_submit(self):
		self.approved_by = frappe.session.user

	def on_submit(self):
		for d in self.items:
			upsert_item_price(d.paper_item, self.price_list, d.new_rate, valid_from=self.effective_from)
		if self.create_revised_costings:
			self.make_revised_costings()

	def make_revised_costings(self):
		new_rates = {d.paper_item: flt(d.new_rate) for d in self.items}
		for row in self.impacts:
			old = frappe.get_doc("Box Costing", row.box_costing)
			new = frappe.copy_doc(old)
			new.amended_from = None
			new.costing_date = self.effective_from
			new.valid_till = None
			new.quoted_price_per_box = 0
			new.remarks = _("Revised for paper price change {0}").format(self.name)
			for p in new.papers:
				if p.paper_item in new_rates:
					p.rate = new_rates[p.paper_item]
			new.insert()
			frappe.db.set_value("Paper Price Revision Impact", row.name, "revised_costing", new.name)
		if self.impacts:
			frappe.msgprint(
				_("{0} revised Box Costings created as drafts. Review and submit them to update customer prices.").format(
					len(self.impacts)
				),
				indicator="green",
			)
