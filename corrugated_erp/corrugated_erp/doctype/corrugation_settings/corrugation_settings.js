// Copyright (c) 2026, Syvasoft Business Solutions and contributors
// For license information, please see license.txt

(() => {
frappe.ui.form.on("Corrugation Settings", {
	setup(frm) {
		["gum_item", "stitch_wire_item", "ink_item", "scrap_item"].forEach((f) =>
			frm.set_query(f, () => ({ filters: { is_stock_item: 1 } }))
		);
		frm.set_query("paper_price_list", () => ({ filters: { buying: 1 } }));
		frm.set_query("selling_price_list", () => ({ filters: { selling: 1 } }));
		["reel_warehouse", "scrap_warehouse"].forEach((f) =>
			frm.set_query(f, () => ({ filters: { is_group: 0, company: frm.doc.company } }))
		);
	},
});

frappe.ui.form.on("Corrugation Standard Deckle", {
	deckle_inch(frm, cdt, cdn) {
		const d = locals[cdt][cdn];
		frappe.model.set_value(cdt, cdn, "deckle_mm", flt(d.deckle_inch * 25.4, 1));
	},
});
})();
