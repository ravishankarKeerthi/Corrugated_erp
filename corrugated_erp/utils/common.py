"""Shared helpers for Corrugated ERP (Frappe-aware)."""

import frappe
from frappe import _
from frappe.utils import flt

from corrugated_erp.utils import corrugation as calc

ACTIVE_REEL_STATUSES = ("In Stock", "Partially Used")


PLANT_FIELDS = (
	"reel_warehouse",
	"scrap_warehouse",
	"paper_price_list",
	"selling_price_list",
	"reel_naming_series",
	"process_waste_pct",
	"conversion_rate_per_kg",
	"print_rate_per_colour_per_1000",
	"gum_rate_per_kg",
	"stitch_rate",
	"scrap_rate_per_kg",
	"overhead_pct",
	"default_margin_pct",
	"min_margin_pct",
)


def get_settings(company=None):
	"""Corrugation Settings, with the company's Corrugation Plant values laid over the defaults.

	Returns a plain dict-like object (attribute access works) so callers cannot accidentally save it.
	"""
	base = frappe.get_cached_doc("Corrugation Settings").as_dict()
	company = company or base.get("company")
	if company and frappe.db.exists("Corrugation Plant", {"name": company, "is_active": 1}):
		plant = frappe.get_cached_doc("Corrugation Plant", company)
		for field in PLANT_FIELDS:
			value = plant.get(field)
			if value not in (None, "", 0, 0.0):
				base[field] = value
		base["plant_name"] = plant.plant_name
	base["company"] = company
	return base


def get_company(company=None):
	return (
		company
		or frappe.db.get_single_value("Corrugation Settings", "company")
		or frappe.defaults.get_user_default("Company")
		or frappe.db.get_single_value("Global Defaults", "default_company")
	)


def standard_deckles(settings=None):
	settings = settings or get_settings()
	return [flt(d.deckle_mm) for d in settings.get("standard_deckles") or [] if d.is_active and flt(d.deckle_mm) > 0]


def best_deckle(sheet_width_mm, settings=None):
	settings = settings or get_settings()
	options = calc.deckle_options(
		[{"width_mm": sheet_width_mm, "outs": 0}], standard_deckles(settings), settings.min_deckle_trim_mm
	)
	return options[0] if options else None


def get_paper_rate(item_code, price_list=None):
	"""Paper rate per kg: price list first, then last purchase rate, then valuation rate."""
	if not item_code:
		return 0.0
	price_list = price_list or get_settings().paper_price_list
	if price_list:
		rate = frappe.db.get_value(
			"Item Price",
			{"item_code": item_code, "price_list": price_list},
			"price_list_rate",
			order_by="valid_from desc, modified desc",
		)
		if rate:
			return flt(rate)
	rate = frappe.db.get_value("Item", item_code, ["last_purchase_rate", "valuation_rate"], as_dict=True) or {}
	return flt(rate.get("last_purchase_rate")) or flt(rate.get("valuation_rate"))


def upsert_item_price(item_code, price_list, rate, customer=None, valid_from=None, uom=None):
	"""Create or update an Item Price row (customer specific when customer is given)."""
	uom = uom or frappe.db.get_value("Item", item_code, "stock_uom")
	filters = {"item_code": item_code, "price_list": price_list, "uom": uom}
	filters["customer"] = customer if customer else ["is", "not set"]
	name = frappe.db.get_value("Item Price", filters, "name", order_by="valid_from desc, modified desc")
	if name:
		doc = frappe.get_doc("Item Price", name)
		doc.price_list_rate = flt(rate)
		if valid_from:
			doc.valid_from = valid_from
	else:
		doc = frappe.get_doc(
			{
				"doctype": "Item Price",
				"item_code": item_code,
				"price_list": price_list,
				"customer": customer,
				"price_list_rate": flt(rate),
				"valid_from": valid_from,
				"uom": uom,
			}
		)
	doc.flags.ignore_permissions = True
	doc.save()
	return doc.name


def validate_kraft_item(item_code, row_label=""):
	item = frappe.db.get_value("Item", item_code, ["is_kraft_paper", "has_batch_no", "is_stock_item"], as_dict=True)
	if not item:
		frappe.throw(_("{0}Item {1} not found").format(row_label, item_code))
	if not item.is_kraft_paper:
		frappe.throw(_("{0}Item {1} is not marked as Kraft Paper").format(row_label, frappe.bold(item_code)))
	if not item.has_batch_no or not item.is_stock_item:
		frappe.throw(
			_("{0}Kraft paper item {1} must be a stock item with 'Has Batch No' enabled so every reel is tracked.").format(
				row_label, frappe.bold(item_code)
			)
		)
