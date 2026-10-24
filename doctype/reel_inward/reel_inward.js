// Copyright (c) 2026, Syvasoft Business Solutions and contributors
// For license information, please see license.txt

(() => {
frappe.ui.form.on("Reel Inward", {
	setup(frm) {
		frm.set_query("paper_item", "reels", () => ({ filters: { is_kraft_paper: 1, disabled: 0 } }));
		frm.set_query("purchase_order", () => ({
			filters: { supplier: frm.doc.supplier, docstatus: 1, status: ["not in", ["Closed", "Completed"]] },
		}));
		frm.set_query("warehouse", () => ({ filters: { is_group: 0, company: frm.doc.company } }));
	},
	onload(frm) {
		if (frm.is_new()) {
			if (!frm.doc.company) frm.set_value("company", frappe.defaults.get_user_default("Company"));
			if (!frm.doc.warehouse) {
				frappe.db.get_single_value("Corrugation Settings", "reel_warehouse").then((v) => v && frm.set_value("warehouse", v));
			}
		}
	},
	refresh(frm) {
		if (frm.doc.purchase_receipt) {
			frm.add_custom_button(__("Purchase Receipt"), () => frappe.set_route("Form", "Purchase Receipt", frm.doc.purchase_receipt), __("View"));
		}
		if (frm.doc.docstatus === 1 && flt(frm.doc.claimable_shortage_kg) > 0) {
			if (frm.doc.debit_note) {
				frm.add_custom_button(__("Shortage Debit Note"), () => frappe.set_route("Form", "Purchase Invoice", frm.doc.debit_note), __("View"));
			} else {
				frm.add_custom_button(__("Shortage Debit Note"), () => {
					frappe.call({
						method: "corrugated_erp.corrugated_erp.doctype.reel_inward.reel_inward.make_shortage_debit_note",
						args: { reel_inward: frm.doc.name },
						freeze: true,
						callback(r) {
							if (r.message) frappe.set_route("Form", "Purchase Invoice", r.message);
						},
					});
				}, __("Create"));
			}
			frm.dashboard.add_indicator(
				__("Weight short {0} kg (claim {1})", [frm.doc.claimable_shortage_kg, format_currency(frm.doc.shortage_amount)]),
				"red"
			);
		}
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__("Reels"), () => frappe.set_route("List", "Paper Reel", { reel_inward: frm.doc.name }), __("View"));
			frm.add_custom_button(__("Print Reel Labels"), () => {
				const names = (frm.doc.reels || []).map((d) => d.reel_no).filter(Boolean);
				const url = frappe.urllib.get_full_url(
					"/api/method/frappe.utils.print_format.download_multi_pdf?" +
					"doctype=" + encodeURIComponent("Paper Reel") +
					"&name=" + encodeURIComponent(JSON.stringify(names)) +
					"&format=" + encodeURIComponent("Reel Label") +
					"&no_letterhead=1"
				);
				window.open(url);
			});
		}
	},
	reels_add: calculate_totals,
	reels_remove: calculate_totals,
});

frappe.ui.form.on("Reel Inward Item", {
	deckle_mm(frm, cdt, cdn) {
		const d = locals[cdt][cdn];
		frappe.model.set_value(cdt, cdn, "deckle_inch", flt(d.deckle_mm / 25.4, 2));
	},
	gross_weight: set_net,
	core_weight: set_net,
	rate(frm, cdt, cdn) {
		const d = locals[cdt][cdn];
		frappe.model.set_value(cdt, cdn, "amount", flt(d.rate * d.net_weight, 2));
		calculate_totals(frm);
	},
});

function set_net(frm, cdt, cdn) {
	const d = locals[cdt][cdn];
	frappe.model.set_value(cdt, cdn, "net_weight", flt(flt(d.gross_weight) - flt(d.core_weight), 3));
	frappe.model.set_value(cdt, cdn, "amount", flt(flt(d.rate) * (flt(d.gross_weight) - flt(d.core_weight)), 2));
	calculate_totals(frm);
}

function calculate_totals(frm) {
	const rows = frm.doc.reels || [];
	frm.set_value("total_reels", rows.length);
	frm.set_value("total_gross_weight", rows.reduce((s, d) => s + flt(d.gross_weight), 0));
	frm.set_value("total_net_weight", rows.reduce((s, d) => s + flt(d.net_weight), 0));
	frm.set_value("total_amount", rows.reduce((s, d) => s + flt(d.amount), 0));
}
})();
