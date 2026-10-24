"""Server side of the Shop Floor Entry page (simple screen for operators on a phone or tablet)."""

import frappe
from frappe import _
from frappe.utils import cint, flt, now_datetime

from corrugated_erp.utils.common import ACTIVE_REEL_STATUSES


@frappe.whitelist()
def get_work_order(work_order):
	frappe.has_permission("Production Entry", "create", throw=True)
	wo = frappe.db.get_value(
		"Work Order",
		work_order,
		["name", "production_item", "item_name", "qty", "produced_qty", "status", "docstatus", "box_spec", "deckle_mm", "outs", "sales_order"],
		as_dict=True,
	)
	if not wo or wo.docstatus != 1:
		frappe.throw(_("Work Order {0} not found or not submitted").format(work_order))
	spec = (
		frappe.db.get_value(
			"Box Specification",
			wo.box_spec,
			["box_name", "customer", "ply", "length_mm", "width_mm", "height_mm", "sheet_length_mm", "sheet_width_mm",
			 "ups_per_sheet", "printing_type", "artwork_status", "boxes_per_bundle"],
			as_dict=True,
		)
		if wo.box_spec
		else None
	) or {}
	stages = frappe.get_all(
		"Production Stage",
		filters={"is_active": 1},
		fields=["name", "sequence", "consumes_reels", "output_in", "default_workstation", "tooling_type"],
		order_by="sequence asc",
	)
	done = {
		r.production_stage: flt(r.qty)
		for r in frappe.db.sql(
			"""select production_stage, sum(output_qty) qty from `tabProduction Entry`
			where work_order=%s and docstatus=1 group by production_stage""",
			work_order,
			as_dict=True,
		)
	}
	next_stage = None
	for s in stages:
		s["done"] = done.get(s.name, 0)
		if not next_stage and s["done"] <= 0:
			next_stage = s.name
	return {"work_order": wo, "spec": spec, "stages": stages, "next_stage": next_stage or (stages[-1].name if stages else None)}


@frappe.whitelist()
def get_reel(reel):
	frappe.has_permission("Paper Reel", "read", throw=True)
	reel = (reel or "").strip()
	row = frappe.db.get_value(
		"Paper Reel",
		reel,
		["name", "paper_item", "item_name", "gsm", "bf", "deckle_mm", "current_weight", "status", "quality_status"],
		as_dict=True,
	)
	if not row:
		frappe.throw(_("Reel {0} not found").format(reel))
	if row.status not in ACTIVE_REEL_STATUSES:
		frappe.throw(_("Reel {0} is {1}").format(reel, row.status))
	if row.quality_status == "Fail":
		frappe.throw(_("Reel {0} failed quality test").format(reel))
	return row


@frappe.whitelist()
def submit_entry(data):
	"""Create (and submit) a Production Entry from the shop floor screen."""
	frappe.has_permission("Production Entry", "create", throw=True)
	data = frappe.parse_json(data)
	pe = frappe.new_doc("Production Entry")
	pe.update(
		{
			"posting_date": data.get("posting_date") or frappe.utils.today(),
			"shift": data.get("shift") or "General",
			"work_order": data.get("work_order"),
			"production_stage": data.get("production_stage"),
			"workstation": data.get("workstation"),
			"operator": data.get("operator"),
			"start_time": data.get("start_time"),
			"end_time": data.get("end_time") or now_datetime(),
			"output_qty": flt(data.get("output_qty")),
			"rejected_qty": flt(data.get("rejected_qty")),
			"contractor": data.get("contractor"),
			"remarks": data.get("remarks"),
		}
	)
	for r in data.get("reels") or []:
		pe.append("reels", {"paper_reel": r.get("paper_reel"), "closing_weight": flt(r.get("closing_weight"))})
	for w in data.get("waste") or []:
		if flt(w.get("qty_kg")) > 0:
			pe.append("waste", {"waste_type": w.get("waste_type"), "qty_kg": flt(w.get("qty_kg"))})
	for d in data.get("downtime") or []:
		if flt(d.get("minutes")) > 0:
			pe.append("downtime", {"reason": d.get("reason"), "minutes": flt(d.get("minutes")), "remarks": d.get("remarks")})
	pe.insert()
	if cint(data.get("submit")):
		pe.submit()
	return {"name": pe.name, "docstatus": pe.docstatus, "box_equivalent": pe.box_equivalent}
