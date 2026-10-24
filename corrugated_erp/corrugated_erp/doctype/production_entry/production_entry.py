# Copyright (c) 2026, Syvasoft Business Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, time_diff_in_hours

from corrugated_erp.utils import corrugation as calc
from corrugated_erp.utils.common import ACTIVE_REEL_STATUSES, get_settings
from corrugated_erp.utils.reel import sync_reel


class ProductionEntry(Document):
	def validate(self):
		self.set_work_order_details()
		self.validate_artwork()
		self.set_box_equivalent()
		self.calculate_time()
		if cint(self.consumes_reels):
			self.validate_reels()
		else:
			self.set("reels", [])
			self.total_reel_consumed_kg = 0
		self.validate_materials()
		self.calculate_waste()
		self.calculate_labour()
		self.validate_tooling()
		self.validate_quantities()
		self.title = "{0} - {1}".format(self.production_stage, self.work_order)

	# ------------------------------------------------------------- validation
	def set_work_order_details(self):
		wo = frappe.db.get_value(
			"Work Order",
			self.work_order,
			["docstatus", "status", "production_item", "box_spec", "sales_order", "qty", "company"],
			as_dict=True,
		)
		if not wo or wo.docstatus != 1:
			frappe.throw(_("Work Order {0} must be submitted").format(self.work_order))
		if wo.status in ("Stopped", "Closed", "Cancelled"):
			frappe.throw(_("Work Order {0} is {1}").format(self.work_order, wo.status))
		self.production_item = wo.production_item
		self.box_spec = wo.box_spec
		self.sales_order = wo.sales_order
		self.wo_qty = wo.qty
		self.company = wo.company
		stage = frappe.db.get_value(
			"Production Stage",
			self.production_stage,
			["stage_type", "consumes_reels", "is_final_stage", "tooling_type", "is_active", "output_in", "piece_rate", "piece_rate_basis"],
			as_dict=True,
		)
		if not stage.is_active:
			frappe.throw(_("Production Stage {0} is not active").format(self.production_stage))
		self.stage_type = stage.stage_type
		self.consumes_reels = stage.consumes_reels
		self.is_final_stage = stage.is_final_stage
		self.tooling_type = stage.tooling_type
		self.output_in = stage.output_in or "Boxes"
		if self.is_new() and not flt(self.piece_rate) and flt(stage.piece_rate):
			self.piece_rate = stage.piece_rate
			self.piece_rate_basis = stage.piece_rate_basis
		self.ups = cint(frappe.db.get_value("Box Specification", self.box_spec, "ups_per_sheet")) if self.box_spec else 1
		self.ups = self.ups or 1

	def validate_artwork(self):
		"""No printing until the customer has approved the artwork (when the setting is on)."""
		if not self.box_spec or not (self.stage_type == "Printing" or self.tooling_type == "Printing Plate"):
			return
		if not cint(get_settings(self.company).block_print_without_artwork):
			return
		printing_type, status = frappe.db.get_value("Box Specification", self.box_spec, ["printing_type", "artwork_status"])
		if printing_type and printing_type != "None" and status != "Approved":
			frappe.throw(
				_("Artwork for {0} is '{1}'. Get customer approval and mark it Approved on the Box Specification before printing.").format(
					frappe.get_desk_link("Box Specification", self.box_spec), status or "Pending"
				),
				title=_("Artwork Not Approved"),
			)

	def set_box_equivalent(self):
		factor = cint(self.ups) if self.output_in == "Sheets" else 1
		self.box_equivalent = flt(self.output_qty) * (factor or 1)

	def calculate_time(self):
		self.duration_hrs = 0
		self.output_per_hour = 0
		self.net_run_hrs = 0
		self.availability_pct = 0
		total_down = 0.0
		for d in self.get("downtime") or []:
			if d.from_time and d.to_time and not flt(d.minutes):
				mins = time_diff_in_hours(d.to_time, d.from_time) * 60
				if mins < 0:
					mins += 24 * 60  # crosses midnight
				d.minutes = flt(mins, 1)
			if flt(d.minutes) < 0:
				frappe.throw(_("Downtime row {0}: minutes cannot be negative").format(d.idx))
			total_down += flt(d.minutes)
		self.total_downtime_min = flt(total_down, 1)
		if self.start_time and self.end_time:
			hrs = time_diff_in_hours(self.end_time, self.start_time)
			if hrs < 0:
				frappe.throw(_("End time is before start time"))
			if total_down / 60.0 > hrs + 0.001:
				frappe.throw(_("Downtime ({0} min) is more than the shift time ({1} hrs)").format(total_down, flt(hrs, 2)))
			res = calc.downtime_summary(hrs, total_down, self.output_qty)
			self.duration_hrs = flt(hrs, 2)
			self.net_run_hrs = res["net_run_hrs"]
			self.output_per_hour = res["output_per_hour"]
			self.availability_pct = res["availability_pct"]

	def validate_materials(self):
		for d in self.get("materials") or []:
			if flt(d.qty) <= 0:
				frappe.throw(_("Materials row {0}: enter the quantity used").format(d.idx))
			if not cint(frappe.db.get_value("Item", d.item_code, "is_stock_item")):
				frappe.throw(_("Materials row {0}: {1} is not a stock item").format(d.idx, d.item_code))
			if frappe.db.get_value("Item", d.item_code, "is_kraft_paper"):
				frappe.throw(_("Materials row {0}: enter paper in the Reels table, not here").format(d.idx))
			d.uom = frappe.db.get_value("Item", d.item_code, "stock_uom")

	def calculate_labour(self):
		self.labour_amount = calc.piece_amount(self.output_qty, self.piece_rate, self.piece_rate_basis) if flt(self.piece_rate) else 0

	def validate_reels(self):
		if not self.reels:
			frappe.throw(_("Enter the reels used in this corrugation run"))
		seen = set()
		total = 0.0
		for r in self.reels:
			label = _("Row {0}: ").format(r.idx)
			if r.paper_reel in seen:
				frappe.throw(label + _("Reel {0} is entered twice").format(r.paper_reel))
			seen.add(r.paper_reel)
			reel = frappe.db.get_value(
				"Paper Reel",
				r.paper_reel,
				["status", "paper_item", "current_weight", "warehouse", "batch_no", "deckle_mm", "quality_status"],
				as_dict=True,
			)
			if reel.status not in ACTIVE_REEL_STATUSES:
				frappe.throw(label + _("Reel {0} is {1}").format(r.paper_reel, reel.status))
			if reel.quality_status == "Fail":
				frappe.throw(
					label + _("Reel {0} failed the incoming quality test. Return it to the supplier or clear the test first.").format(r.paper_reel)
				)
			r.paper_item = reel.paper_item
			r.batch_no = reel.batch_no
			r.warehouse = reel.warehouse
			r.deckle_mm = reel.deckle_mm
			if self.docstatus == 0:
				r.opening_weight = flt(reel.current_weight)
			closing = flt(r.closing_weight)
			if closing < 0 or closing > flt(r.opening_weight):
				frappe.throw(label + _("Balance weight must be between 0 and {0} kg").format(r.opening_weight))
			r.consumed_kg = flt(flt(r.opening_weight) - closing, 3)
			if r.consumed_kg <= 0:
				frappe.throw(label + _("Nothing consumed from reel {0}").format(r.paper_reel))
			if flt(self.deckle_mm) and flt(reel.deckle_mm) and flt(reel.deckle_mm) != flt(self.deckle_mm):
				frappe.msgprint(
					label + _("Reel deckle {0} mm differs from run deckle {1} mm").format(reel.deckle_mm, self.deckle_mm),
					indicator="orange",
				)
			total += r.consumed_kg
		self.total_reel_consumed_kg = flt(total, 3)

	def calculate_waste(self):
		self.total_waste_kg = flt(sum(flt(d.qty_kg) for d in self.waste), 3)

	def validate_tooling(self):
		if not self.tooling_type:
			self.tooling = None
			return
		if not self.tooling and self.box_spec:
			field = "die_tooling" if self.tooling_type == "Die" else "plate_tooling"
			self.tooling = frappe.db.get_value("Box Specification", self.box_spec, field)
		if self.tooling:
			tt, status = frappe.db.get_value("Box Tooling", self.tooling, ["tooling_type", "status"])
			if tt != self.tooling_type:
				frappe.throw(_("{0} is not a {1}").format(self.tooling, self.tooling_type))
			if status in ("Scrapped", "Under Repair"):
				frappe.throw(_("{0} {1} is {2}").format(self.tooling_type, self.tooling, status))

	def validate_quantities(self):
		if flt(self.output_qty) <= 0:
			frappe.throw(_("Good output must be greater than zero"))
		if flt(self.rejected_qty) < 0:
			frappe.throw(_("Rejected qty cannot be negative"))
		seq = frappe.db.get_value("Production Stage", self.production_stage, "sequence")
		prev_stage = frappe.db.sql(
			"""select pe.production_stage, sum(pe.box_equivalent) qty
			from `tabProduction Entry` pe join `tabProduction Stage` ps on ps.name = pe.production_stage
			where pe.work_order=%s and pe.docstatus=1 and ps.sequence < %s
			group by pe.production_stage, ps.sequence order by ps.sequence desc limit 1""",
			(self.work_order, seq),
			as_dict=True,
		)
		if prev_stage:
			done = flt(
				frappe.db.sql(
					"""select sum(box_equivalent) from `tabProduction Entry`
					where work_order=%s and production_stage=%s and docstatus=1 and name!=%s""",
					(self.work_order, self.production_stage, self.name or ""),
				)[0][0]
			)
			if done + flt(self.box_equivalent) > flt(prev_stage[0].qty):
				frappe.msgprint(
					_("Output at {0} ({1} boxes) is more than the output booked at {2} ({3} boxes).").format(
						self.production_stage, done + flt(self.box_equivalent), prev_stage[0].production_stage, prev_stage[0].qty
					),
					indicator="orange",
					title=_("Check Quantity"),
				)

	# ------------------------------------------------------------- submit
	def on_submit(self):
		if (cint(self.consumes_reels) and self.reels) or self.get("materials"):
			self.make_reel_transfer()
		self.update_tooling(1)
		self.make_scrap_entry()
		if cint(self.is_final_stage):
			self.make_manufacture_entry()

	def on_cancel(self):
		self.ignore_linked_doctypes = ("Stock Entry", "Stock Ledger Entry")
		for field in ("manufacture_entry", "scrap_entry", "material_transfer_entry"):
			name = self.get(field)
			if not name or not frappe.db.exists("Stock Entry", name):
				continue
			se = frappe.get_doc("Stock Entry", name)
			se.flags.ignore_permissions = True
			if se.docstatus == 1:
				se.cancel()
			elif se.docstatus == 0:
				frappe.delete_doc("Stock Entry", name, ignore_permissions=True)
				self.db_set(field, None)
		self.update_tooling(-1)
		for r in self.reels:
			sync_reel(r.paper_reel)

	def get_work_order(self):
		return frappe.get_doc("Work Order", self.work_order)

	def make_reel_transfer(self):
		wo = self.get_work_order()
		if cint(wo.skip_transfer):
			frappe.throw(
				_(
					"Work Order {0} has 'Skip Material Transfer to WIP' enabled. Disable it so reel consumption can be transferred."
				).format(wo.name)
			)
		if not wo.wip_warehouse:
			frappe.throw(_("Set the Work-in-Progress warehouse on Work Order {0}").format(wo.name))
		pending = max(flt(wo.qty) - flt(wo.material_transferred_for_manufacturing), 0)
		se = frappe.new_doc("Stock Entry")
		se.update(
			{
				"stock_entry_type": "Material Transfer for Manufacture",
				"purpose": "Material Transfer for Manufacture",
				"work_order": wo.name,
				"bom_no": wo.bom_no,
				"from_bom": 0,
				"fg_completed_qty": min(flt(self.box_equivalent), pending) if pending else 0,
				"company": wo.company,
				"posting_date": self.posting_date,
				"set_posting_time": 1,
				"to_warehouse": wo.wip_warehouse,
				"production_entry": self.name,
				"remarks": _("Paper and materials used in {0}").format(self.name),
			}
		)
		for m in self.get("materials") or []:
			se.append(
				"items",
				{
					"item_code": m.item_code,
					"qty": m.qty,
					"uom": m.uom,
					"stock_uom": m.uom,
					"conversion_factor": 1,
					"s_warehouse": m.s_warehouse,
					"t_warehouse": wo.wip_warehouse,
				},
			)
		for r in self.reels:
			uom = frappe.db.get_value("Item", r.paper_item, "stock_uom")
			se.append(
				"items",
				{
					"item_code": r.paper_item,
					"qty": r.consumed_kg,
					"uom": uom,
					"stock_uom": uom,
					"conversion_factor": 1,
					"s_warehouse": r.warehouse,
					"t_warehouse": wo.wip_warehouse,
					"batch_no": r.batch_no,
					"use_serial_batch_fields": 1,
				},
			)
		se.flags.ignore_permissions = True
		try:
			se.insert()
			se.submit()
		except Exception:
			frappe.log_error(title="Corrugated ERP reel transfer failed", reference_doctype=self.doctype, reference_name=self.name)
			raise
		self.db_set("material_transfer_entry", se.name)

	def make_manufacture_entry(self):
		from erpnext.manufacturing.doctype.work_order.work_order import make_stock_entry

		s = get_settings(self.company)
		data = make_stock_entry(self.work_order, "Manufacture", flt(self.output_qty))
		se = frappe.get_doc(data)
		se.posting_date = self.posting_date
		se.set_posting_time = 1
		se.production_entry = self.name
		se.flags.ignore_permissions = True
		se.insert()
		if cint(s.auto_submit_manufacture_entry):
			se.submit()
		else:
			frappe.msgprint(
				_("Finished goods entry {0} created as draft. Review the paper back-flush and submit it.").format(
					frappe.get_desk_link("Stock Entry", se.name)
				),
				indicator="blue",
			)
		self.db_set("manufacture_entry", se.name)

	def make_scrap_entry(self):
		s = get_settings(self.company)
		if not (cint(s.create_scrap_receipt) and s.scrap_item and s.scrap_warehouse and flt(self.total_waste_kg) > 0):
			return
		se = frappe.new_doc("Stock Entry")
		se.update(
			{
				"stock_entry_type": "Material Receipt",
				"purpose": "Material Receipt",
				"company": self.company,
				"posting_date": self.posting_date,
				"set_posting_time": 1,
				"production_entry": self.name,
				"remarks": _("Production waste from {0}").format(self.name),
			}
		)
		se.append(
			"items",
			{
				"item_code": s.scrap_item,
				"qty": self.total_waste_kg,
				"t_warehouse": s.scrap_warehouse,
				"basic_rate": flt(s.scrap_rate_per_kg),
				"allow_zero_valuation_rate": 0 if flt(s.scrap_rate_per_kg) else 1,
			},
		)
		se.flags.ignore_permissions = True
		se.insert()
		se.submit()
		self.db_set("scrap_entry", se.name)

	def update_tooling(self, sign):
		if not self.tooling:
			return
		# one impression per sheet / blank through the press or die
		impressions = int(flt(self.output_qty) + flt(self.rejected_qty))
		tooling = frappe.db.get_value("Box Tooling", self.tooling, ["impressions_used", "impressions_life"], as_dict=True)
		used = max(0, int(tooling.impressions_used or 0) + sign * impressions)
		life = int(tooling.impressions_life or 0)
		values = {"impressions_used": used, "utilisation_pct": flt(used / life * 100, 2) if life else 0}
		if sign > 0:
			values["last_used_on"] = self.posting_date
		frappe.db.set_value("Box Tooling", self.tooling, values, update_modified=False)
		if sign > 0 and life and used >= 0.9 * life:
			frappe.msgprint(
				_("{0} {1} has used {2}% of its life").format(self.tooling_type, self.tooling, values["utilisation_pct"]),
				indicator="orange",
			)


@frappe.whitelist()
def get_reel_details(reel):
	return frappe.db.get_value(
		"Paper Reel",
		reel,
		["paper_item", "current_weight", "batch_no", "warehouse", "deckle_mm", "status", "gsm", "bf"],
		as_dict=True,
	)
