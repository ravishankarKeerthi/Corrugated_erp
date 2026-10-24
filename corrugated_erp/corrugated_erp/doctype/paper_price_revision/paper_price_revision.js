// Copyright (c) 2026, Syvasoft Business Solutions and contributors
// For license information, please see license.txt

(() => {
frappe.ui.form.on("Paper Price Revision", {
	setup(frm) {
		frm.set_query("paper_item", "items", () => ({ filters: { is_kraft_paper: 1 } }));
		frm.set_query("price_list", () => ({ filters: { buying: 1 } }));
	},
	onload(frm) {
		if (frm.is_new() && !frm.doc.price_list) {
			frappe.db.get_single_value("Corrugation Settings", "paper_price_list").then((v) => v && frm.set_value("price_list", v));
		}
	},
	refresh(frm) {
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Add All Kraft Papers"), () => {
				frappe.db.get_list("Item", { filters: { is_kraft_paper: 1, disabled: 0 }, pluck: "name", limit: 500 }).then((items) => {
					const have = new Set((frm.doc.items || []).map((d) => d.paper_item));
					items.filter((i) => !have.has(i)).forEach((i) => frm.add_child("items", { paper_item: i }));
					frm.refresh_field("items");
				});
			});
			frm.add_custom_button(__("Calculate Impact"), () => frm.save());
		}
		if (frm.doc.specs_affected) {
			frm.dashboard.clear_headline();
			frm.dashboard.set_headline(
				__("{0} box specifications affected, average cost change {1}%", [frm.doc.specs_affected, frm.doc.avg_cost_change_pct])
			);
		}
	},
});

frappe.ui.form.on("Paper Price Revision Item", {
	new_rate(frm, cdt, cdn) {
		const d = locals[cdt][cdn];
		if (d.current_rate) {
			frappe.model.set_value(cdt, cdn, "change_pct", flt((d.new_rate / d.current_rate - 1) * 100, 2));
		}
	},
});
})();
