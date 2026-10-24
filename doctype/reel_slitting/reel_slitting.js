// Copyright (c) 2026, Syvasoft Business Solutions and contributors
// For license information, please see license.txt

(() => {
frappe.ui.form.on("Reel Slitting", {
	setup(frm) {
		frm.set_query("parent_reel", () => ({ filters: { status: ["in", ["In Stock", "Partially Used"]] } }));
	},
	onload(frm) {
		if (frm.is_new() && !frm.doc.company) {
			frm.set_value("company", frappe.defaults.get_user_default("Company"));
		}
	},
	refresh(frm) {
		if (frm.doc.docstatus === 0 && (frm.doc.outputs || []).length) {
			frm.add_custom_button(__("Recalculate Weights"), () => {
				(frm.doc.outputs || []).forEach((d) => (d.weight_kg = 0));
				split(frm);
			});
		}
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__("New Reels"), () => frappe.set_route("List", "Paper Reel", { reel_slitting: frm.doc.name }), __("View"));
			frm.add_custom_button(__("Print Reel Labels"), () => {
				const names = (frm.doc.outputs || []).map((d) => d.reel_no).filter(Boolean);
				window.open(frappe.urllib.get_full_url(
					"/api/method/frappe.utils.print_format.download_multi_pdf?doctype=" + encodeURIComponent("Paper Reel") +
					"&name=" + encodeURIComponent(JSON.stringify(names)) + "&format=" + encodeURIComponent("Reel Label") + "&no_letterhead=1"
				));
			});
		}
	},
	parent_reel(frm) {
		frm.set_value("slit_weight_kg", 0);
		setTimeout(() => {
			if (!flt(frm.doc.slit_weight_kg)) frm.set_value("slit_weight_kg", frm.doc.parent_weight_kg);
		}, 500);
	},
	slit_weight_kg(frm) {
		(frm.doc.outputs || []).forEach((d) => (d.weight_kg = 0));
		split(frm);
	},
});

frappe.ui.form.on("Reel Slitting Output", {
	deckle_mm(frm, cdt, cdn) {
		const d = locals[cdt][cdn];
		d.deckle_inch = flt(d.deckle_mm / 25.4, 2);
		(frm.doc.outputs || []).forEach((r) => (r.weight_kg = 0));
		split(frm);
	},
	weight_kg: totals,
	outputs_remove: split,
});

function split(frm) {
	const rows = (frm.doc.outputs || []).filter((d) => flt(d.deckle_mm) > 0);
	if (!rows.length || !flt(frm.doc.slit_weight_kg) || !flt(frm.doc.parent_deckle_mm)) return;
	frappe.call({
		method: "corrugated_erp.corrugated_erp.doctype.reel_slitting.reel_slitting.split_weights",
		args: {
			parent_weight_kg: frm.doc.slit_weight_kg,
			parent_deckle_mm: frm.doc.parent_deckle_mm,
			deckles: rows.map((d) => d.deckle_mm),
		},
		callback(r) {
			if (!r.message) return;
			rows.forEach((d, i) => {
				if (!flt(d.weight_kg)) d.weight_kg = r.message.child_weights[i];
				d.deckle_inch = flt(d.deckle_mm / 25.4, 2);
			});
			frm.doc.used_deckle_mm = r.message.used_deckle_mm;
			frm.doc.trim_deckle_mm = r.message.trim_deckle_mm;
			totals(frm);
		},
	});
}

function totals(frm) {
	const total = (frm.doc.outputs || []).reduce((a, d) => a + flt(d.weight_kg), 0);
	frm.doc.total_output_kg = flt(total, 3);
	frm.doc.trim_weight_kg = flt(flt(frm.doc.slit_weight_kg) - total, 3);
	frm.refresh_fields();
}
})();
