# Copyright (c) 2026, Syvasoft Business Solutions and contributors
# For license information, please see license.txt

"""Paper needed for open box Work Orders, by paper and reel deckle, against reels in stock.

Standard MRP looks at the paper item only; a corrugation plant also needs the right deckle.
"Wider reels" can be cut down with Reel Slitting; open purchase orders are per paper item.
"""

import frappe
from frappe import _
from frappe.utils import flt

from corrugated_erp.utils import corrugation as calc
from corrugated_erp.utils.common import ACTIVE_REEL_STATUSES, get_settings


def execute(filters=None):
	filters = frappe._dict(filters or {})
	waste_pct = flt(get_settings(filters.get("company")).process_waste_pct)
	wo_filters = {
		"docstatus": 1,
		"status": ["in", ["Not Started", "In Process"]],
		"box_spec": ["is", "set"],
	}
	if filters.get("company"):
		wo_filters["company"] = filters.company
	if filters.get("to_date"):
		wo_filters["planned_start_date"] = ["<=", filters.to_date + " 23:59:59"]
	work_orders = frappe.get_all(
		"Work Order", filters=wo_filters, fields=["name", "qty", "box_spec", "deckle_mm", "planned_start_date"]
	)
	needs = {}
	for wo in work_orders:
		corrugated = flt(
			frappe.db.sql(
				"""select sum(pe.box_equivalent) from `tabProduction Entry` pe
				where pe.work_order=%s and pe.docstatus=1 and pe.consumes_reels=1""",
				wo.name,
			)[0][0]
		)
		remaining = max(flt(wo.qty) - corrugated, 0)
		if not remaining:
			continue
		spec = frappe.db.get_value("Box Specification", wo.box_spec, ["suggested_deckle_mm"], as_dict=True) or {}
		deckle = flt(wo.deckle_mm) or flt(spec.get("suggested_deckle_mm"))
		layers = frappe.get_all(
			"Box Spec Layer", filters={"parent": wo.box_spec, "parenttype": "Box Specification"}, fields=["paper_item", "weight_g"]
		)
		kgs = calc.paper_required_kg([d.weight_g for d in layers], remaining, waste_pct)
		for layer, kg in zip(layers, kgs):
			if not layer.paper_item:
				continue
			key = (layer.paper_item, deckle)
			row = needs.setdefault(key, {"required_kg": 0.0, "work_orders": set()})
			row["required_kg"] += kg
			row["work_orders"].add(wo.name)

	open_po = {
		r.item_code: flt(r.qty)
		for r in frappe.db.sql(
			"""select poi.item_code, sum((poi.qty - poi.received_qty) * poi.conversion_factor) qty
			from `tabPurchase Order Item` poi join `tabPurchase Order` po on po.name = poi.parent
			where po.docstatus = 1 and po.status not in ('Closed', 'Completed', 'On Hold')
				and poi.qty > poi.received_qty
			group by poi.item_code""",
			as_dict=True,
		)
	}
	data = []
	for (item, deckle), need in sorted(needs.items()):
		reels = frappe.get_all(
			"Paper Reel",
			filters={"paper_item": item, "status": ["in", ACTIVE_REEL_STATUSES], "quality_status": ["!=", "Fail"]},
			fields=["deckle_mm", "current_weight"],
		)
		exact = sum(flt(r.current_weight) for r in reels if abs(flt(r.deckle_mm) - deckle) < 0.5)
		wider = sum(flt(r.current_weight) for r in reels if flt(r.deckle_mm) > deckle + 0.5)
		required = flt(need["required_kg"], 1)
		shortage = max(required - exact, 0)
		if filters.get("only_shortage") and not shortage:
			continue
		item_info = frappe.db.get_value("Item", item, ["paper_gsm", "paper_bf", "item_name"], as_dict=True) or {}
		data.append(
			{
				"paper_item": item,
				"item_name": item_info.get("item_name"),
				"gsm": item_info.get("paper_gsm"),
				"bf": item_info.get("paper_bf"),
				"deckle_mm": deckle,
				"deckle_inch": calc.mm_to_inch(deckle),
				"required_kg": required,
				"stock_exact_kg": flt(exact, 1),
				"stock_wider_kg": flt(wider, 1),
				"open_po_kg": flt(open_po.get(item), 1),
				"shortage_kg": flt(shortage, 1),
				"work_orders": ", ".join(sorted(need["work_orders"])),
			}
		)
	columns = [
		{"label": _("Paper"), "fieldname": "paper_item", "fieldtype": "Link", "options": "Item", "width": 160},
		{"label": _("GSM"), "fieldname": "gsm", "fieldtype": "Float", "width": 60},
		{"label": _("BF"), "fieldname": "bf", "fieldtype": "Float", "width": 55},
		{"label": _("Deckle (mm)"), "fieldname": "deckle_mm", "fieldtype": "Float", "width": 95},
		{"label": _("Deckle (in)"), "fieldname": "deckle_inch", "fieldtype": "Float", "width": 85},
		{"label": _("Required (kg)"), "fieldname": "required_kg", "fieldtype": "Float", "width": 110},
		{"label": _("Stock - Same Deckle"), "fieldname": "stock_exact_kg", "fieldtype": "Float", "width": 140},
		{"label": _("Stock - Wider (can cut)"), "fieldname": "stock_wider_kg", "fieldtype": "Float", "width": 155},
		{"label": _("Open PO (any deckle)"), "fieldname": "open_po_kg", "fieldtype": "Float", "width": 145},
		{"label": _("Shortage (kg)"), "fieldname": "shortage_kg", "fieldtype": "Float", "width": 110},
		{"label": _("Work Orders"), "fieldname": "work_orders", "fieldtype": "Data", "width": 250},
	]
	return columns, data
