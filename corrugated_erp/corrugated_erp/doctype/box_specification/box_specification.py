# Copyright (c) 2026, Syvasoft Business Solutions and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt

from corrugated_erp.utils import corrugation as calc
from corrugated_erp.utils.common import best_deckle, get_company, get_settings, standard_deckles

CALCULATED_FIELDS = (
	"board_gsm",
	"caliper_mm",
	"sheet_length_mm",
	"sheet_width_mm",
	"sheet_area_sqm",
	"sheet_weight_g",
	"sheet_length_inch",
	"sheet_width_inch",
	"box_weight_g",
	"theoretical_bs",
	"estimated_bct_kgf",
	"gum_kg_per_box",
	"suggested_deckle_mm",
	"suggested_deckle_inch",
	"outs_on_reel",
	"deckle_trim_pct",
	"dimension_inch",
)


class BoxSpecification(Document):
	def validate(self):
		self.validate_dimensions()
		if not self.get("layers"):
			self.build_layers()
		self.validate_layers()
		self.calculate()
		self.validate_tooling()
		self.validate_strength()
		self.validate_artwork()

	def on_update(self):
		"""A spec change after the BOM exists creates a new revision and BOM; open Work Orders keep the old BOM."""
		if self.flags.in_bom_creation or not (self.item_code and self.bom):
			return
		before = self.get_doc_before_save()
		if not before or spec_signature(before) == spec_signature(self):
			if before and flt(before.box_weight_g) != flt(self.box_weight_g):
				set_kg_conversion(self.item_code, self.box_weight_g)
			return
		if any(not d.paper_item for d in self.layers):
			frappe.msgprint(
				_("The specification changed but a new BOM was not made because some layers have no paper item."),
				indicator="orange",
			)
			return
		bom = make_bom(self)
		self.db_set({"bom": bom.name, "revision": cint(self.revision) + 1})
		frappe.db.set_value("Item", self.item_code, "description", self.get_description())
		set_kg_conversion(self.item_code, self.box_weight_g)
		open_wos = frappe.get_all(
			"Work Order",
			filters={"production_item": self.item_code, "docstatus": ["<", 2], "status": ["not in", ["Completed", "Stopped", "Closed", "Cancelled"]]},
			pluck="name",
		)
		msg = _("Specification changed: revision {0} with new BOM {1} created.").format(self.revision, bom.name)
		if open_wos:
			msg += "<br>" + _("Open Work Orders still use the previous BOM: {0}").format(", ".join(open_wos))
		frappe.msgprint(msg, indicator="blue", title=_("New Revision"))
	# ------------------------------------------------------------------ checks
	def validate_dimensions(self):
		method = frappe.db.get_value("Box Style", self.box_style, "sheet_length_method")
		self.sheet_length_method = method
		if method == "Manual":
			if not (flt(self.manual_sheet_length_mm) and flt(self.manual_sheet_width_mm)):
				frappe.throw(_("Box style {0} needs the sheet length and width entered manually").format(self.box_style))
		for field in ("length_mm", "width_mm", "height_mm"):
			if flt(self.get(field)) <= 0 and method != "Manual":
				frappe.throw(_("{0} must be greater than zero").format(self.meta.get_label(field)))

	def build_layers(self):
		self.set("layers", [])
		for row in get_layer_template(self.ply, self.flute_1, self.flute_2, self.flute_3):
			self.append("layers", row)

	def validate_layers(self):
		expected = 2 * calc.flute_count(cint(self.ply) or 3) + 1
		if len(self.layers) != expected:
			frappe.throw(
				_("A {0}-ply board must have {1} layers. Use 'Rebuild Layers' after changing ply.").format(self.ply, expected)
			)
		for d in self.layers:
			if flt(d.gsm) <= 0:
				frappe.throw(_("Row {0}: enter GSM for {1}").format(d.idx, d.layer_name))
			if calc.is_flute(d.layer_type):
				if not d.flute_type:
					frappe.throw(_("Row {0}: select the flute type for {1}").format(d.idx, d.layer_name))
				if not flt(d.take_up_factor):
					d.take_up_factor = flt(frappe.db.get_value("Flute Type", d.flute_type, "take_up_factor")) or 1.4
			else:
				d.flute_type = None
				d.take_up_factor = 1

	def validate_tooling(self):
		for field, tooling_type in (("die_tooling", "Die"), ("plate_tooling", "Printing Plate")):
			if self.get(field):
				tt, status = frappe.db.get_value("Box Tooling", self.get(field), ["tooling_type", "status"])
				if tt != tooling_type:
					frappe.throw(_("{0} must be a tooling of type {1}").format(self.meta.get_label(field), tooling_type))
				if status == "Scrapped":
					frappe.msgprint(_("{0} {1} is scrapped").format(tooling_type, self.get(field)), indicator="orange")

	def validate_artwork(self):
		if not self.printing_type or self.printing_type == "None":
			return
		if not self.artwork_status:
			self.artwork_status = "Pending"
		if self.artwork_status == "Approved":
			if not self.artwork:
				frappe.throw(_("Attach the artwork before marking it approved"))
			if not self.artwork_approved_on:
				self.artwork_approved_on = frappe.utils.today()
		before = self.get_doc_before_save()
		if before and before.artwork and self.artwork != before.artwork and self.artwork_status == "Approved":
			# a new artwork file must be approved again
			self.artwork_status = "Pending"
			self.artwork_approved_on = None
			frappe.msgprint(_("New artwork attached - approval status reset to Pending"), indicator="orange")

	def validate_strength(self):
		if flt(self.required_bs) and flt(self.theoretical_bs) < flt(self.required_bs):
			frappe.msgprint(
				_("Theoretical BS {0} kg/cm² is below the required {1} kg/cm². Consider higher BF or GSM paper.").format(
					self.theoretical_bs, self.required_bs
				),
				indicator="orange",
				title=_("Strength Warning"),
			)
		if flt(self.required_bct_kgf) and flt(self.estimated_bct_kgf) and flt(self.estimated_bct_kgf) < flt(self.required_bct_kgf):
			frappe.msgprint(
				_("Estimated BCT {0} kgf is below the required {1} kgf.").format(self.estimated_bct_kgf, self.required_bct_kgf),
				indicator="orange",
				title=_("Strength Warning"),
			)

	# ------------------------------------------------------------------ maths
	def calculate(self):
		s = get_settings()
		style = frappe.db.get_value(
			"Box Style", self.box_style, ["sheet_length_method", "top_flap_factor", "bottom_flap_factor"], as_dict=True
		) or frappe._dict()
		flute_heights = {}
		layers = []
		for d in self.layers:
			if d.flute_type and d.flute_type not in flute_heights:
				flute_heights[d.flute_type] = flt(frappe.db.get_value("Flute Type", d.flute_type, "flute_height_mm"))
			layers.append(
				{
					"layer_type": d.layer_type,
					"gsm": flt(d.gsm),
					"bf": flt(d.bf),
					"take_up_factor": flt(d.take_up_factor) or 1,
					"flute_height_mm": flute_heights.get(d.flute_type, 0),
				}
			)
		res = calc.compute_spec(
			{
				"length_mm": self.length_mm,
				"width_mm": self.width_mm,
				"height_mm": self.height_mm,
				"dimension_basis": self.dimension_basis,
				"method": style.sheet_length_method or "Wrap Around",
				"top_flap_factor": style.top_flap_factor,
				"bottom_flap_factor": style.bottom_flap_factor,
				"glue_flap_mm": s.glue_flap_mm,
				"length_allowance_mm": s.length_allowance_mm,
				"width_allowance_mm": s.width_allowance_mm,
				"manual_length_mm": self.manual_sheet_length_mm,
				"manual_width_mm": self.manual_sheet_width_mm,
				"liner_thickness_mm": s.liner_thickness_mm,
				"caliper_override_mm": self.caliper_override_mm,
				"ect_kn_per_m": self.ect_kn_per_m,
				"gum_gsm_per_glue_line": s.gum_gsm_per_glue_line,
				"ups": cint(self.ups_per_sheet) or 1,
				"layers": layers,
			}
		)
		for d, lr in zip(self.layers, res["layers"]):
			d.effective_gsm = lr["effective_gsm"]
			d.weight_g = lr["weight_g"]
		for key in (
			"board_gsm",
			"sheet_length_mm",
			"sheet_width_mm",
			"sheet_area_sqm",
			"sheet_weight_g",
			"sheet_length_inch",
			"sheet_width_inch",
			"box_weight_g",
			"theoretical_bs",
			"estimated_bct_kgf",
			"gum_kg_per_box",
		):
			self.set(key, res[key])
		self.caliper_mm = res["caliper_mm"]
		self.dimension_inch = "{0} x {1} x {2} in".format(
			calc.mm_to_inch(self.length_mm), calc.mm_to_inch(self.width_mm), calc.mm_to_inch(self.height_mm)
		)
		best = best_deckle(self.sheet_width_mm, s) if standard_deckles(s) else None
		if best:
			self.suggested_deckle_mm = best["deckle_mm"]
			self.suggested_deckle_inch = best["deckle_inch"]
			self.outs_on_reel = best["outs"][0]
			self.deckle_trim_pct = best["trim_pct"]
		else:
			self.suggested_deckle_mm = self.suggested_deckle_inch = self.outs_on_reel = self.deckle_trim_pct = 0

	def get_description(self):
		flutes = "".join(f for f in (self.flute_1, self.flute_2, self.flute_3) if f)
		text = "{style} {l} x {w} x {h} mm ({basis}), {ply} Ply {flutes} Flute, Board {gsm} GSM".format(
			style=self.box_style,
			l=flt(self.length_mm),
			w=flt(self.width_mm),
			h=flt(self.height_mm),
			basis=self.dimension_basis,
			ply=self.ply,
			flutes=flutes,
			gsm=flt(self.board_gsm, 0),
		)
		if self.printing_type and self.printing_type != "None":
			text += ", {0} colour {1} print".format(cint(self.no_of_colours), self.printing_type)
		if cint(self.ups_per_sheet) > 1:
			text += ", {0} ups per sheet".format(cint(self.ups_per_sheet))
		return text


SIGNATURE_FIELDS = (
	"box_style", "dimension_basis", "length_mm", "width_mm", "height_mm", "manual_sheet_length_mm",
	"manual_sheet_width_mm", "ply", "flute_1", "flute_2", "flute_3", "ups_per_sheet", "printing_type",
	"no_of_colours", "joint_type", "stitches_per_box", "caliper_override_mm",
)


def spec_signature(doc):
	"""Fields that change the bill of materials."""
	head = tuple(str(doc.get(f) or "") for f in SIGNATURE_FIELDS)
	layers = tuple((d.layer_name, d.paper_item or "", flt(d.gsm), flt(d.take_up_factor, 3)) for d in doc.get("layers") or [])
	return head + layers


def set_kg_conversion(item_code, box_weight_g):
	"""Keep a Kg UOM on the box item: 1 Kg = 1000 / box weight (g) boxes, so orders and invoices can be in Kg."""
	if not item_code or flt(box_weight_g) <= 0 or not frappe.db.exists("UOM", "Kg"):
		return
	factor = flt(1000.0 / flt(box_weight_g), 6)
	item = frappe.get_doc("Item", item_code)
	row = next((d for d in item.get("uoms") or [] if d.uom == "Kg"), None)
	if row and flt(row.conversion_factor, 6) == factor:
		return
	if row:
		row.conversion_factor = factor
	else:
		item.append("uoms", {"uom": "Kg", "conversion_factor": factor})
	item.flags.ignore_permissions = True
	item.save()


# ---------------------------------------------------------------------- API
@frappe.whitelist()
def get_layer_template(ply, flute_1=None, flute_2=None, flute_3=None):
	try:
		rows = calc.build_layer_template(cint(ply) or 3, [flute_1, flute_2, flute_3])
	except ValueError as e:
		frappe.throw(str(e))
	for row in rows:
		row["take_up_factor"] = (
			flt(frappe.db.get_value("Flute Type", row["flute_type"], "take_up_factor")) if row["flute_type"] else 1
		)
	return rows


@frappe.whitelist()
def get_calculated(doc):
	"""Live recalculation for the form without saving."""
	if isinstance(doc, str):
		doc = json.loads(doc)
	spec = frappe.get_doc(doc)
	if not spec.box_style or not spec.get("layers"):
		return {}
	# silent version of validate_layers: never throw while the user is still typing
	for d in spec.layers:
		if calc.is_flute(d.layer_type):
			if d.flute_type and not flt(d.take_up_factor):
				d.take_up_factor = flt(frappe.db.get_value("Flute Type", d.flute_type, "take_up_factor")) or 1.4
		else:
			d.take_up_factor = 1
	spec.calculate()
	return {
		"fields": {f: spec.get(f) for f in CALCULATED_FIELDS},
		"layers": [
			{"idx": d.idx, "take_up_factor": d.take_up_factor, "effective_gsm": d.effective_gsm, "weight_g": d.weight_g}
			for d in spec.layers
		],
	}


@frappe.whitelist()
def get_deckle_options(sheet_width_mm):
	s = get_settings()
	return calc.deckle_options([{"width_mm": flt(sheet_width_mm), "outs": 0}], standard_deckles(s), s.min_deckle_trim_mm)[:10]


@frappe.whitelist()
def create_item_and_bom(box_spec):
	"""Create (or reuse) the finished box Item and a fresh default BOM per 1000 boxes."""
	spec = frappe.get_doc("Box Specification", box_spec)
	spec.check_permission("write")
	if spec.status == "Obsolete":
		frappe.throw(_("Box Specification {0} is obsolete").format(spec.name))
	s = get_settings()
	missing = [d.layer_name for d in spec.layers if not d.paper_item]
	if missing:
		frappe.throw(_("Select a paper item for: {0}").format(", ".join(missing)))

	if not spec.item_code or not frappe.db.exists("Item", spec.item_code):
		item_code = "{0}{1}".format(s.box_item_prefix or "", spec.name)
		if not frappe.db.exists("Item", item_code):
			item = frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": item_code,
					"item_name": spec.box_name[:140],
					"item_group": s.box_item_group or "Corrugated Boxes",
					"stock_uom": "Nos",
					"is_stock_item": 1,
					"include_item_in_manufacturing": 1,
					"description": spec.get_description(),
					"box_spec": spec.name,
				}
			)
			if spec.customer:
				item.append(
					"customer_items", {"customer_name": spec.customer, "ref_code": spec.customer_item_code or spec.box_name}
				)
			item.insert()
		spec.db_set("item_code", item_code)
	else:
		frappe.db.set_value("Item", spec.item_code, {"box_spec": spec.name, "description": spec.get_description()})
	set_kg_conversion(spec.item_code, spec.box_weight_g)
	if spec.pricing_basis == "Per Kg" and frappe.db.exists("UOM", "Kg"):
		frappe.db.set_value("Item", spec.item_code, "sales_uom", "Kg")

	bom = make_bom(spec, s)
	spec.db_set({"bom": bom.name, "revision": cint(spec.revision) + 1})
	return {"item_code": spec.item_code, "bom": bom.name}


def make_bom(spec, s=None):
	s = s or get_settings()
	per = 1000.0
	waste = 1 + flt(s.process_waste_pct) / 100.0
	qty_by_item = {}
	for d in spec.layers:
		kg = flt(d.weight_g) / 1000.0 * per * waste
		qty_by_item[d.paper_item] = qty_by_item.get(d.paper_item, 0) + kg
	if s.gum_item and flt(spec.gum_kg_per_box):
		qty_by_item[s.gum_item] = qty_by_item.get(s.gum_item, 0) + flt(spec.gum_kg_per_box) * per
	if s.stitch_wire_item and cint(spec.stitches_per_box) and spec.joint_type == "Stitched":
		qty_by_item[s.stitch_wire_item] = cint(spec.stitches_per_box) * flt(s.wire_g_per_stitch) / 1000.0 * per
	if s.ink_item and cint(spec.no_of_colours) and spec.printing_type != "None":
		qty_by_item[s.ink_item] = cint(spec.no_of_colours) * flt(s.ink_g_per_colour_per_box) / 1000.0 * per

	bom = frappe.new_doc("BOM")
	bom.item = spec.item_code
	bom.company = get_company()
	bom.quantity = per
	bom.is_active = 1
	bom.is_default = 1
	if s.paper_price_list:
		bom.rm_cost_as_per = "Price List"
		bom.buying_price_list = s.paper_price_list
	else:
		bom.rm_cost_as_per = "Valuation Rate"
	for item_code, qty in qty_by_item.items():
		uom = frappe.db.get_value("Item", item_code, "stock_uom")
		bom.append("items", {"item_code": item_code, "qty": flt(qty, 4), "uom": uom, "stock_uom": uom, "conversion_factor": 1})
	bom.insert()
	bom.submit()
	return bom
