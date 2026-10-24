# Copyright (c) 2026, Syvasoft Business Solutions and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, now_datetime

from corrugated_erp.utils import corrugation as calc
from corrugated_erp.utils.common import get_paper_rate, get_settings, upsert_item_price

RESULT_FIELDS = (
	"paper_cost_per_box",
	"waste_cost_per_box",
	"conversion_cost_per_box",
	"printing_cost_per_box",
	"tooling_cost_per_box",
	"stitching_cost_per_box",
	"gum_cost_per_box",
	"manufacturing_cost_per_box",
	"overhead_cost_per_box",
	"total_cost_per_box",
	"cost_per_kg",
	"selling_price_per_box",
	"price_per_kg",
	"margin_per_box",
)


class BoxCosting(Document):
	def before_insert(self):
		self.set_defaults_from_settings()

	def validate(self):
		spec = frappe.get_doc("Box Specification", self.box_spec)
		if spec.status == "Obsolete":
			frappe.throw(_("Box Specification {0} is obsolete").format(spec.name))
		if not self.get("papers"):
			self.load_from_spec(spec)
		self.set_box_data(spec)
		self.set_paper_rates()
		self.calculate()
		self.set_approval_status()

	def before_submit(self):
		self.check_margin_approval()

	def on_submit(self):
		frappe.db.set_value(
			"Box Specification",
			self.box_spec,
			{
				"latest_costing": self.name,
				"latest_cost_per_box": self.total_cost_per_box,
				"latest_price_per_box": self.final_price_per_box,
			},
		)
		if self.update_price_list:
			self.update_customer_price()

	def on_cancel(self):
		if frappe.db.get_value("Box Specification", self.box_spec, "latest_costing") == self.name:
			prev = frappe.get_all(
				"Box Costing",
				filters={"box_spec": self.box_spec, "docstatus": 1, "name": ["!=", self.name]},
				fields=["name", "total_cost_per_box", "final_price_per_box"],
				order_by="costing_date desc, creation desc",
				limit=1,
			)
			p = prev[0] if prev else frappe._dict()
			frappe.db.set_value(
				"Box Specification",
				self.box_spec,
				{
					"latest_costing": p.get("name"),
					"latest_cost_per_box": p.get("total_cost_per_box") or 0,
					"latest_price_per_box": p.get("final_price_per_box") or 0,
				},
			)

	# ---------------------------------------------------------------- setup
	def set_defaults_from_settings(self):
		s = get_settings(self.get("company"))
		defaults = {
			"waste_pct": s.process_waste_pct,
			"conversion_rate_per_kg": s.conversion_rate_per_kg,
			"print_rate_per_colour_per_1000": s.print_rate_per_colour_per_1000,
			"stitch_rate": s.stitch_rate,
			"gum_rate": s.gum_rate_per_kg,
			"overhead_pct": s.overhead_pct,
			"margin_pct": s.default_margin_pct,
			"selling_price_list": s.selling_price_list,
		}
		for field, value in defaults.items():
			if not self.get(field) and value:
				self.set(field, value)

	def load_from_spec(self, spec):
		s = get_settings(self.get("company"))
		price_list = s.paper_price_list
		self.set("papers", [])
		for d in spec.layers:
			self.append(
				"papers",
				{
					"layer_name": d.layer_name,
					"paper_item": d.paper_item,
					"gsm": d.gsm,
					"bf": d.bf,
					"weight_kg": flt(d.weight_g) / 1000.0,
					"rate": get_paper_rate(d.paper_item, price_list) if d.paper_item else 0,
				},
			)
		self.no_of_colours = cint(spec.no_of_colours) if spec.printing_type != "None" else 0
		self.stitches_per_box = cint(spec.stitches_per_box) if spec.joint_type == "Stitched" else 0
		for field, tooling in (("plate", spec.plate_tooling), ("die", spec.die_tooling)):
			if tooling and not flt(self.get(field + "_cost")):
				cost, life = frappe.db.get_value("Box Tooling", tooling, ["cost", "impressions_life"])
				self.set(field + "_cost", flt(cost))
				self.set(field + "_amortise_qty", cint(life) or cint(s.tooling_amortise_qty))

	def set_box_data(self, spec):
		self.box_weight_g = spec.box_weight_g
		self.box_weight_kg = flt(spec.box_weight_g) / 1000.0
		self.sheet_area_sqm = spec.sheet_area_sqm
		self.gum_kg_per_box = spec.gum_kg_per_box
		self.item_code = spec.item_code
		if not self.pricing_basis:
			self.pricing_basis = spec.pricing_basis or "Per Box"

	def set_paper_rates(self):
		price_list = get_settings(self.get("company")).paper_price_list
		for d in self.papers:
			if d.paper_item and not flt(d.rate):
				d.rate = get_paper_rate(d.paper_item, price_list)

	# ---------------------------------------------------------------- maths
	def cost_inputs(self, rate_overrides=None):
		rate_overrides = rate_overrides or {}
		return {
			"papers": [
				{"weight_kg": d.weight_kg, "rate": rate_overrides.get(d.paper_item, d.rate)} for d in self.get("papers") or []
			],
			"waste_pct": self.waste_pct,
			"box_weight_kg": self.box_weight_kg or flt(self.box_weight_g) / 1000.0,
			"conversion_rate_per_kg": self.conversion_rate_per_kg,
			"colours": self.no_of_colours,
			"print_rate_per_colour_per_1000": self.print_rate_per_colour_per_1000,
			"plate_cost": self.plate_cost,
			"plate_amortise_qty": self.plate_amortise_qty,
			"die_cost": self.die_cost,
			"die_amortise_qty": self.die_amortise_qty,
			"stitches": self.stitches_per_box,
			"stitch_rate": self.stitch_rate,
			"gum_kg": self.gum_kg_per_box,
			"gum_rate": self.gum_rate,
			"other_cost_per_box": self.other_cost_per_box,
			"overhead_pct": self.overhead_pct,
			"freight_per_box": self.freight_per_box,
			"margin_pct": self.margin_pct,
			"quantity": self.quantity,
		}

	def calculate(self):
		res = calc.compute_cost(self.cost_inputs())
		for d, amount in zip(self.papers, res["paper_rows"]):
			d.amount = amount
		for field in RESULT_FIELDS:
			self.set(field, res[field])
		weight_kg = flt(self.box_weight_kg) or flt(self.box_weight_g) / 1000.0
		if self.pricing_basis == "Per Kg" and flt(self.quoted_price_per_kg):
			self.final_price_per_box = calc.price_from_kg_rate(self.quoted_price_per_kg, weight_kg)
		else:
			self.final_price_per_box = flt(self.quoted_price_per_box) or flt(self.selling_price_per_box)
		self.achieved_margin_pct = calc.achieved_margin_pct(self.final_price_per_box, self.total_cost_per_box)
		self.order_value = flt(self.final_price_per_box * flt(self.quantity), 2)
		if flt(self.final_price_per_box) and flt(self.final_price_per_box) < flt(self.total_cost_per_box):
			frappe.msgprint(_("Final price is below cost"), indicator="red", title=_("Loss Warning"))

	# ---------------------------------------------------------------- approval
	def set_approval_status(self):
		self.min_margin_pct = flt(get_settings(self.get("company")).min_margin_pct)
		if flt(self.achieved_margin_pct) >= flt(self.min_margin_pct):
			self.approval_status = "Not Required"
			self.approved_by = self.approved_on = None
		elif self.approval_status != "Approved":
			self.approval_status = "Pending Approval"

	def check_margin_approval(self):
		if self.approval_status != "Pending Approval":
			return
		role = get_settings(self.get("company")).margin_approver_role or "Sales Manager"
		if role in frappe.get_roles():
			self.approval_status = "Approved"
			self.approved_by = frappe.session.user
			self.approved_on = now_datetime()
			return
		frappe.throw(
			_("Margin {0}% is below the minimum {1}%. A user with role {2} must submit this costing.").format(
				flt(self.achieved_margin_pct, 2), flt(self.min_margin_pct, 2), frappe.bold(role)
			),
			title=_("Approval Needed"),
		)

	def update_customer_price(self):
		if not self.item_code:
			frappe.msgprint(
				_("Create the box Item from the Box Specification to update the price list"), indicator="orange"
			)
			return
		price_list = self.selling_price_list or get_settings(self.get("company")).selling_price_list
		if not price_list:
			return
		upsert_item_price(
			self.item_code, price_list, self.final_price_per_box, customer=self.customer, valid_from=self.costing_date, uom="Nos"
		)
		if self.pricing_basis == "Per Kg" and flt(self.box_weight_kg):
			rate_per_kg = flt(self.quoted_price_per_kg) or flt(self.final_price_per_box) / flt(self.box_weight_kg)
			upsert_item_price(
				self.item_code, price_list, flt(rate_per_kg, 2), customer=self.customer, valid_from=self.costing_date, uom="Kg"
			)


@frappe.whitelist()
def get_costing_values(doc):
	"""Live recalculation for the form (no save)."""
	if isinstance(doc, str):
		doc = json.loads(doc)
	costing = frappe.get_doc(doc)
	costing.calculate()
	costing.set_approval_status()
	out = {
		f: costing.get(f)
		for f in RESULT_FIELDS + ("final_price_per_box", "achieved_margin_pct", "order_value", "approval_status", "min_margin_pct")
	}
	out["papers"] = [{"idx": d.idx, "amount": d.amount} for d in costing.papers]
	return out


@frappe.whitelist()
def make_costing(box_spec, company=None):
	spec = frappe.get_doc("Box Specification", box_spec)
	doc = frappe.new_doc("Box Costing")
	doc.box_spec = spec.name
	doc.customer = spec.customer
	doc.company = company or frappe.defaults.get_user_default("Company")
	doc.pricing_basis = spec.pricing_basis or "Per Box"
	doc.set_defaults_from_settings()
	doc.load_from_spec(spec)
	doc.set_box_data(spec)
	doc.calculate()
	return doc


@frappe.whitelist()
def get_latest_price(box_spec, customer=None):
	filters = {"box_spec": box_spec, "docstatus": 1}
	if customer:
		filters["customer"] = customer
	row = frappe.get_all(
		"Box Costing",
		filters=filters,
		fields=["name", "final_price_per_box"],
		order_by="costing_date desc, creation desc",
		limit=1,
	)
	return row[0] if row else None
