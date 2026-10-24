"""Whitelisted helpers used by client scripts on standard ERPNext forms."""

import json

import frappe
from frappe import _
from frappe.utils import add_days, flt, today


@frappe.whitelist()
def get_box_prices(items, customer=None):
	"""Latest submitted Box Costing price for each box spec (customer specific first).

	items: list (or JSON) of {"name": row name, "box_spec": ...}
	"""
	if isinstance(items, str):
		items = json.loads(items)
	out = {}
	for row in items or []:
		spec = row.get("box_spec")
		if not spec:
			continue
		price = None
		for filters in ({"box_spec": spec, "docstatus": 1, "customer": customer}, {"box_spec": spec, "docstatus": 1}):
			if not filters.get("customer", True):
				continue
			found = frappe.get_all(
				"Box Costing",
				filters=filters,
				fields=["name", "final_price_per_box"],
				order_by="costing_date desc, creation desc",
				limit=1,
			)
			if found:
				price = found[0]
				break
		if price:
			out[row.get("name")] = {"rate": flt(price.final_price_per_box), "box_costing": price.name}
	return out


@frappe.whitelist()
def get_spec_summary(box_spec):
	return frappe.db.get_value(
		"Box Specification",
		box_spec,
		[
			"box_name",
			"box_style",
			"ply",
			"length_mm",
			"width_mm",
			"height_mm",
			"board_gsm",
			"box_weight_g",
			"sheet_length_mm",
			"sheet_width_mm",
			"suggested_deckle_mm",
			"outs_on_reel",
		],
		as_dict=True,
	)


@frappe.whitelist()
def make_paper_material_request(rows, company=None):
	"""Purchase Material Request for the shortages shown in Paper Requirement Planning."""
	frappe.has_permission("Material Request", "create", throw=True)
	if isinstance(rows, str):
		rows = json.loads(rows)
	company = company or frappe.defaults.get_user_default("Company")
	from corrugated_erp.utils.common import get_settings

	warehouse = get_settings(company).reel_warehouse
	mr = frappe.new_doc("Material Request")
	mr.material_request_type = "Purchase"
	mr.company = company
	mr.transaction_date = today()
	mr.schedule_date = add_days(today(), 7)
	for row in rows or []:
		qty = flt(row.get("shortage_kg"))
		if qty <= 0 or not row.get("paper_item"):
			continue
		mr.append(
			"items",
			{
				"item_code": row["paper_item"],
				"qty": qty,
				"schedule_date": mr.schedule_date,
				"warehouse": warehouse,
				"description": _("{0} - deckle {1} mm ({2} in). For: {3}").format(
					row.get("item_name") or row["paper_item"], row.get("deckle_mm"), row.get("deckle_inch"), row.get("work_orders") or ""
				),
			},
		)
	if not mr.get("items"):
		frappe.throw(_("No shortage to order"))
	mr.run_method("set_missing_values")
	mr.insert()
	return mr.name


# ---------------------------------------------------------------- dashboard number cards
@frappe.whitelist()
def card_paper_stock_value(filters=None):
	"""Value of kraft paper in stock (from the stock ledger)."""
	value = frappe.db.sql(
		"""select sum(b.stock_value) from `tabBin` b join `tabItem` i on i.name = b.item_code
		where i.is_kraft_paper = 1"""
	)[0][0]
	return {"value": flt(value), "fieldtype": "Currency"}


@frappe.whitelist()
def card_waste_pct_this_month(filters=None):
	from frappe.utils import get_first_day

	row = frappe.db.sql(
		"""select sum(total_waste_kg), sum(total_reel_consumed_kg) from `tabProduction Entry`
		where docstatus = 1 and posting_date >= %s""",
		get_first_day(today()),
	)[0]
	waste, paper = flt(row[0]), flt(row[1])
	return {"value": flt(waste / paper * 100, 2) if paper else 0, "fieldtype": "Percent"}


@frappe.whitelist()
def card_jobs_below_margin(filters=None):
	"""Active box specs whose latest costing margin is below the minimum margin."""
	from corrugated_erp.utils.common import get_settings

	minimum = flt(get_settings().min_margin_pct)
	value = frappe.db.sql(
		"""select count(*) from `tabBox Specification` bs join `tabBox Costing` bc on bc.name = bs.latest_costing
		where bs.status = 'Active' and bc.achieved_margin_pct < %s""",
		minimum,
	)[0][0]
	return {"value": value or 0, "fieldtype": "Int"}


@frappe.whitelist()
def card_box_output_today(filters=None):
	value = frappe.db.sql(
		"""select sum(pe.output_qty) from `tabProduction Entry` pe
		where pe.docstatus = 1 and pe.is_final_stage = 1 and pe.posting_date = %s""",
		today(),
	)[0][0]
	return {"value": flt(value), "fieldtype": "Float"}
