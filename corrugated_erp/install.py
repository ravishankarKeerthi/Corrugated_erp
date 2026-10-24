"""Install / migrate hooks: custom fields on ERPNext doctypes and default masters."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

MODULE = "Corrugated ERP"


def _box_spec_link(insert_after, **extra):
	field = {
		"fieldname": "box_spec",
		"label": "Box Specification",
		"fieldtype": "Link",
		"options": "Box Specification",
		"insert_after": insert_after,
		"fetch_from": "item_code.box_spec",
		"read_only": 1,
		"module": MODULE,
	}
	field.update(extra)
	return field


def get_custom_fields():
	return {
		"Item": [
			{
				"fieldname": "sc_corrugation_section",
				"label": "Corrugation",
				"fieldtype": "Section Break",
				"insert_after": "description",
				"collapsible": 1,
				"module": MODULE,
			},
			{
				"fieldname": "is_kraft_paper",
				"label": "Is Kraft Paper (Reel)",
				"fieldtype": "Check",
				"insert_after": "sc_corrugation_section",
				"module": MODULE,
			},
			{
				"fieldname": "paper_gsm",
				"label": "Paper GSM",
				"fieldtype": "Float",
				"insert_after": "is_kraft_paper",
				"depends_on": "is_kraft_paper",
				"module": MODULE,
			},
			{
				"fieldname": "paper_bf",
				"label": "Paper BF",
				"fieldtype": "Float",
				"insert_after": "paper_gsm",
				"depends_on": "is_kraft_paper",
				"module": MODULE,
			},
			{
				"fieldname": "paper_shade",
				"label": "Paper Shade",
				"fieldtype": "Select",
				"options": "\nNatural\nGolden\nSemi-Golden\nWhite\nDuplex\nVirgin Kraft",
				"insert_after": "paper_bf",
				"depends_on": "is_kraft_paper",
				"module": MODULE,
			},
			{
				"fieldname": "sc_corrugation_cb",
				"fieldtype": "Column Break",
				"insert_after": "paper_shade",
				"module": MODULE,
			},
			{
				"fieldname": "box_spec",
				"label": "Box Specification",
				"fieldtype": "Link",
				"options": "Box Specification",
				"insert_after": "sc_corrugation_cb",
				"read_only": 1,
				"module": MODULE,
			},
		],
		"Quotation Item": [_box_spec_link("item_name")],
		"Sales Order Item": [_box_spec_link("item_name")],
		"Sales Invoice Item": [_box_spec_link("item_name")],
		"Delivery Note Item": [
			_box_spec_link("item_name"),
			{
				"fieldname": "boxes_per_bundle",
				"label": "Boxes per Bundle",
				"fieldtype": "Int",
				"insert_after": "qty",
				"fetch_from": "box_spec.boxes_per_bundle",
				"fetch_if_empty": 1,
				"module": MODULE,
			},
			{
				"fieldname": "no_of_bundles",
				"label": "No. of Bundles",
				"fieldtype": "Float",
				"insert_after": "boxes_per_bundle",
				"read_only": 1,
				"module": MODULE,
			},
		],
		"Delivery Note": [
			{
				"fieldname": "total_bundles",
				"label": "Total Bundles",
				"fieldtype": "Float",
				"insert_after": "total_qty",
				"read_only": 1,
				"module": MODULE,
			}
		],
		"Work Order": [
			{
				"fieldname": "box_spec",
				"label": "Box Specification",
				"fieldtype": "Link",
				"options": "Box Specification",
				"insert_after": "bom_no",
				"read_only": 1,
				"module": MODULE,
			},
			{
				"fieldname": "sheet_length_mm",
				"label": "Sheet Length (mm)",
				"fieldtype": "Float",
				"insert_after": "box_spec",
				"read_only": 1,
				"module": MODULE,
			},
			{
				"fieldname": "sheet_width_mm",
				"label": "Sheet Width (mm)",
				"fieldtype": "Float",
				"insert_after": "sheet_length_mm",
				"read_only": 1,
				"module": MODULE,
			},
			{
				"fieldname": "ups",
				"label": "Ups per Sheet",
				"fieldtype": "Int",
				"insert_after": "sheet_width_mm",
				"read_only": 1,
				"module": MODULE,
			},
			{
				"fieldname": "sheets_required",
				"label": "Sheets Required",
				"fieldtype": "Int",
				"insert_after": "ups",
				"read_only": 1,
				"module": MODULE,
			},
			{
				"fieldname": "deckle_mm",
				"label": "Reel Deckle (mm)",
				"fieldtype": "Float",
				"insert_after": "sheets_required",
				"allow_on_submit": 1,
				"module": MODULE,
			},
			{
				"fieldname": "outs",
				"label": "Outs",
				"fieldtype": "Int",
				"insert_after": "deckle_mm",
				"allow_on_submit": 1,
				"module": MODULE,
			},
			{
				"fieldname": "deckle_plan",
				"label": "Deckle Plan",
				"fieldtype": "Link",
				"options": "Deckle Plan",
				"insert_after": "outs",
				"read_only": 1,
				"allow_on_submit": 1,
				"module": MODULE,
			},
		],
		"Purchase Receipt": [
			{
				"fieldname": "reel_inward",
				"label": "Reel Inward",
				"fieldtype": "Link",
				"options": "Reel Inward",
				"insert_after": "supplier",
				"read_only": 1,
				"no_copy": 1,
				"module": MODULE,
			}
		],
		"Stock Entry": [
			{
				"fieldname": "production_entry",
				"label": "Production Entry",
				"fieldtype": "Link",
				"options": "Production Entry",
				"insert_after": "work_order",
				"read_only": 1,
				"no_copy": 1,
				"module": MODULE,
			}
		],
	}


FLUTES = [
	# code, height mm, take-up factor, flutes per metre
	("A", 4.8, 1.54, 110),
	("C", 3.6, 1.43, 130),
	("B", 2.6, 1.36, 155),
	("E", 1.2, 1.27, 295),
	("F", 0.8, 1.25, 420),
]

BOX_STYLES = [
	# code, name, fefco, method, top, bottom
	("RSC", "Regular Slotted Container", "0201", "Wrap Around", 0.5, 0.5),
	("HSC", "Half Slotted Container", "0200", "Wrap Around", 0.5, 0.0),
	("FOL", "Full Overlap Container", "0203", "Wrap Around", 1.0, 1.0),
	("TRAY", "Tray / Die-Cut Box", "0400 series", "Manual", 0, 0),
	("SHEET", "Board Sheet / Pad", "0900 series", "Manual", 0, 0),
	("PARTITION", "Partition / Divider", "0900 series", "Manual", 0, 0),
]

STAGES = [
	# name, seq, type, consumes reels, final, tooling, output counted in
	("Corrugation", 10, "Corrugation", 1, 0, "", "Sheets"),
	("Pasting", 20, "Pasting", 0, 0, "", "Sheets"),
	("Sheet Cutting", 30, "Sheet Cutting", 0, 0, "", "Sheets"),
	("Printing", 40, "Printing", 0, 0, "Printing Plate", "Sheets"),
	("Slotting & Creasing", 50, "Slotting & Creasing", 0, 0, "", "Boxes"),
	("Die Cutting", 60, "Die Cutting", 0, 0, "Die", "Boxes"),
	("Stitching / Gluing", 70, "Stitching / Gluing", 0, 0, "", "Boxes"),
	("Bundling & Packing", 80, "Bundling & Packing", 0, 1, "", "Boxes"),
]

QUALITY_PARAMETERS = [
	# name, uom, type, applies to
	("Bursting Strength", "kg/cm²", "Numeric", "Both"),
	("Box Compression Strength", "kgf", "Numeric", "Box"),
	("Edge Crush Test", "kN/m", "Numeric", "Box"),
	("Board GSM", "g/m²", "Numeric", "Box"),
	("Paper GSM", "g/m²", "Numeric", "Paper"),
	("Paper BF", "BF", "Numeric", "Paper"),
	("Moisture", "%", "Numeric", "Both"),
	("Cobb Value", "g/m²", "Numeric", "Paper"),
	("Length", "mm", "Numeric", "Box"),
	("Width", "mm", "Numeric", "Box"),
	("Height", "mm", "Numeric", "Box"),
	("Print Registration", "", "Visual", "Box"),
	("Joint / Stitching Quality", "", "Visual", "Box"),
]

ITEM_GROUPS = ["Kraft Paper", "Corrugated Boxes", "Corrugation Consumables"]


def after_install():
	create_custom_fields(get_custom_fields(), update=True)
	create_item_groups()
	create_masters()
	set_default_settings()
	update_manufacturing_settings()
	frappe.db.commit()


def after_migrate():
	create_custom_fields(get_custom_fields(), update=True)
	set_stage_output_defaults()


def set_stage_output_defaults():
	"""Upgrade from 0.1: stages created before 'Output Counted In' existed."""
	for name, _seq, _type, _reels, _final, _tooling, output_in in STAGES:
		if frappe.db.exists("Production Stage", name) and not frappe.db.get_value("Production Stage", name, "output_in"):
			frappe.db.set_value("Production Stage", name, "output_in", output_in, update_modified=False)


def create_item_groups():
	from frappe.utils.nestedset import get_root_of

	parent = get_root_of("Item Group") or "All Item Groups"
	for name in ITEM_GROUPS:
		if not frappe.db.exists("Item Group", name):
			frappe.get_doc({"doctype": "Item Group", "item_group_name": name, "parent_item_group": parent, "is_group": 0}).insert(
				ignore_permissions=True
			)


def create_masters():
	for code, height, take_up, per_m in FLUTES:
		if not frappe.db.exists("Flute Type", code):
			frappe.get_doc(
				{
					"doctype": "Flute Type",
					"flute_code": code,
					"flute_height_mm": height,
					"take_up_factor": take_up,
					"flutes_per_metre": per_m,
					"description": "Typical values - adjust to your corrugator rolls.",
				}
			).insert(ignore_permissions=True)

	for code, name, fefco, method, top, bottom in BOX_STYLES:
		if not frappe.db.exists("Box Style", code):
			frappe.get_doc(
				{
					"doctype": "Box Style",
					"style_code": code,
					"style_name": name,
					"fefco_code": fefco,
					"sheet_length_method": method,
					"top_flap_factor": top,
					"bottom_flap_factor": bottom,
				}
			).insert(ignore_permissions=True)

	for name, seq, stage_type, reels, final, tooling, output_in in STAGES:
		if not frappe.db.exists("Production Stage", name):
			frappe.get_doc(
				{
					"doctype": "Production Stage",
					"stage_name": name,
					"sequence": seq,
					"stage_type": stage_type,
					"consumes_reels": reels,
					"is_final_stage": final,
					"tooling_type": tooling,
					"output_in": output_in,
					"is_active": 1,
				}
			).insert(ignore_permissions=True)

	for name, uom, reading_type, applies in QUALITY_PARAMETERS:
		if not frappe.db.exists("Box Quality Parameter", name):
			frappe.get_doc(
				{
					"doctype": "Box Quality Parameter",
					"parameter_name": name,
					"uom": uom,
					"reading_type": reading_type,
					"applies_to": applies,
				}
			).insert(ignore_permissions=True)


def set_default_settings():
	settings = frappe.get_single("Corrugation Settings")
	settings.paper_item_group = settings.paper_item_group or "Kraft Paper"
	settings.box_item_group = settings.box_item_group or "Corrugated Boxes"
	settings.company = settings.company or frappe.db.get_single_value("Global Defaults", "default_company")
	if frappe.db.exists("Price List", "Standard Buying") and not settings.paper_price_list:
		settings.paper_price_list = "Standard Buying"
	if frappe.db.exists("Price List", "Standard Selling") and not settings.selling_price_list:
		settings.selling_price_list = "Standard Selling"
	if not settings.get("standard_deckles"):
		for inch in range(28, 74, 2):
			settings.append("standard_deckles", {"deckle_inch": inch, "deckle_mm": round(inch * 25.4, 1), "is_active": 1})
	settings.flags.ignore_mandatory = True
	settings.save(ignore_permissions=True)


def update_manufacturing_settings():
	"""Reel consumption is booked through 'Material Transfer for Manufacture', so finished
	goods must back-flush what was actually transferred, with some allowance for waste."""
	ms = frappe.get_single("Manufacturing Settings")
	changed = False
	if ms.get("backflush_raw_materials_based_on") != "Material Transferred for Manufacture":
		ms.backflush_raw_materials_based_on = "Material Transferred for Manufacture"
		changed = True
	# v16 has a separate allowance for extra material transfer; v15 falls back to the overproduction %
	if ms.meta.has_field("transfer_extra_materials_percentage") and not ms.get("transfer_extra_materials_percentage"):
		ms.transfer_extra_materials_percentage = 20
		changed = True
	if changed:
		ms.flags.ignore_mandatory = True
		ms.save(ignore_permissions=True)
