// Copyright (c) 2026, Syvasoft Business Solutions and contributors
// For license information, please see license.txt

(() => {
frappe.ui.form.on("Box Quality Test", {
	setup(frm) {
		frm.set_query("parameter", "readings", () => {
			const applies = frm.doc.test_type === "Incoming Paper" ? ["Paper", "Both"] : ["Box", "Both"];
			return { filters: { applies_to: ["in", applies] } };
		});
	},
	refresh(frm) {
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Get Specification Limits"), () => load_parameters(frm, true));
		}
	},
	onload(frm) {
		if (frm.is_new() && !(frm.doc.readings || []).length && (frm.doc.box_spec || frm.doc.paper_reel)) {
			load_parameters(frm, false);
		}
	},
	box_spec(frm) { load_parameters(frm, false); },
	paper_reel(frm) { load_parameters(frm, false); },
	test_type(frm) { load_parameters(frm, false); },
});

frappe.ui.form.on("Box Quality Test Reading", {
	observed_value: evaluate,
	visual_result: evaluate,
	min_value: evaluate,
	max_value: evaluate,
});

function evaluate(frm, cdt, cdn) {
	const d = locals[cdt][cdn];
	let result = "";
	if (d.reading_type === "Visual") {
		result = d.visual_result === "OK" ? "Pass" : d.visual_result === "Not OK" ? "Fail" : "";
	} else if (d.observed_value || d.observed_value === 0) {
		result = "Pass";
		if (d.min_value && flt(d.observed_value) < flt(d.min_value)) result = "Fail";
		if (d.max_value && flt(d.observed_value) > flt(d.max_value)) result = "Fail";
	}
	frappe.model.set_value(cdt, cdn, "result", result);
	const results = (frm.doc.readings || []).map((r) => r.result);
	frm.set_value("overall_result", results.includes("Fail") ? "Fail" : results.length && results.every(Boolean) ? "Pass" : "Pending");
}

function load_parameters(frm, force) {
	if (!force && (frm.doc.readings || []).length) return;
	if (frm.doc.test_type === "Incoming Paper" ? !frm.doc.paper_reel : !frm.doc.box_spec) return;
	frappe.call({
		method: "corrugated_erp.corrugated_erp.doctype.box_quality_test.box_quality_test.get_parameters",
		args: { test_type: frm.doc.test_type, box_spec: frm.doc.box_spec, paper_reel: frm.doc.paper_reel },
		callback(r) {
			frm.clear_table("readings");
			(r.message || []).forEach((row) => frm.add_child("readings", row));
			frm.refresh_field("readings");
		},
	});
}
})();
