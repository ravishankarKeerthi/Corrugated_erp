# Copyright (c) 2026, Syvasoft Business Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from corrugated_erp.utils.common import get_settings


class BoxQualityTest(Document):
	def validate(self):
		if self.test_type == "Incoming Paper":
			if not self.paper_reel:
				frappe.throw(_("Select the Paper Reel being tested"))
			self.box_spec = None
			if not self.reel_inward:
				self.reel_inward = frappe.db.get_value("Paper Reel", self.paper_reel, "reel_inward")
		elif not self.box_spec:
			frappe.throw(_("Select the Box Specification"))
		self.evaluate()

	def evaluate(self):
		results = []
		for d in self.readings:
			reading_type = d.reading_type or frappe.db.get_value("Box Quality Parameter", d.parameter, "reading_type")
			if reading_type == "Visual":
				d.result = {"OK": "Pass", "Not OK": "Fail"}.get(d.visual_result, "")
			elif d.observed_value in (None, "") or (not flt(d.observed_value) and not flt(d.min_value)):
				d.result = ""
			else:
				ok = True
				if d.min_value not in (None, "") and flt(d.min_value) and flt(d.observed_value) < flt(d.min_value):
					ok = False
				if d.max_value not in (None, "") and flt(d.max_value) and flt(d.observed_value) > flt(d.max_value):
					ok = False
				d.result = "Pass" if ok else "Fail"
			results.append(d.result)
		if "Fail" in results:
			self.overall_result = "Fail"
		elif results and all(results):
			self.overall_result = "Pass"
		else:
			self.overall_result = "Pending"

	def before_submit(self):
		if self.overall_result == "Pending":
			frappe.throw(_("Enter all readings before submitting"))

	def on_submit(self):
		if self.paper_reel:
			frappe.db.set_value("Paper Reel", self.paper_reel, "quality_status", self.overall_result)

	def on_cancel(self):
		if self.paper_reel:
			frappe.db.set_value("Paper Reel", self.paper_reel, "quality_status", "Pending")


def _row(parameter, min_value=None, max_value=None):
	return {"parameter": parameter, "min_value": min_value, "max_value": max_value}


@frappe.whitelist()
def get_parameters(test_type, box_spec=None, paper_reel=None):
	"""Readings pre-filled with limits from the Box Specification or the reel's paper item."""
	s = get_settings()
	rows = []
	if test_type == "Incoming Paper":
		if not paper_reel:
			return rows
		reel = frappe.db.get_value("Paper Reel", paper_reel, ["gsm", "bf"], as_dict=True)
		tol = flt(s.gsm_tolerance_pct) / 100.0
		rows.append(_row("Paper GSM", flt(reel.gsm * (1 - tol), 1), flt(reel.gsm * (1 + tol), 1)))
		rows.append(_row("Paper BF", flt(reel.bf) or None))
		rows.append(_row("Moisture", None, flt(s.moisture_max_pct) or None))
		rows.append(_row("Cobb Value"))
		return rows

	if not box_spec:
		return rows
	spec = frappe.db.get_value(
		"Box Specification",
		box_spec,
		[
			"length_mm",
			"width_mm",
			"height_mm",
			"board_gsm",
			"required_bs",
			"theoretical_bs",
			"required_bct_kgf",
			"ect_kn_per_m",
			"moisture_max_pct",
			"printing_type",
			"joint_type",
		],
		as_dict=True,
	)
	tol_mm = flt(s.dimension_tolerance_mm)
	tol = flt(s.gsm_tolerance_pct) / 100.0
	for parameter, value in (("Length", spec.length_mm), ("Width", spec.width_mm), ("Height", spec.height_mm)):
		rows.append(_row(parameter, flt(value) - tol_mm, flt(value) + tol_mm))
	rows.append(_row("Board GSM", flt(spec.board_gsm * (1 - tol), 1), flt(spec.board_gsm * (1 + tol), 1)))
	rows.append(_row("Bursting Strength", flt(spec.required_bs) or flt(spec.theoretical_bs) or None))
	if flt(spec.required_bct_kgf):
		rows.append(_row("Box Compression Strength", flt(spec.required_bct_kgf)))
	if flt(spec.ect_kn_per_m):
		rows.append(_row("Edge Crush Test", flt(spec.ect_kn_per_m)))
	rows.append(_row("Moisture", None, flt(spec.moisture_max_pct) or flt(s.moisture_max_pct) or None))
	if spec.printing_type and spec.printing_type != "None":
		rows.append(_row("Print Registration"))
	if spec.joint_type in ("Stitched", "Glued"):
		rows.append(_row("Joint / Stitching Quality"))
	for r in rows:
		r["uom"], r["reading_type"] = frappe.db.get_value("Box Quality Parameter", r["parameter"], ["uom", "reading_type"]) or (
			"",
			"Numeric",
		)
	return rows
