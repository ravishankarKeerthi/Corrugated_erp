// Copyright (c) 2026, Syvasoft Business Solutions and contributors
// For license information, please see license.txt

(() => {
frappe.ui.form.on("Paper Reel", {
	refresh(frm) {
		if (frm.is_new()) return;
		const age = frm.doc.__onload && frm.doc.__onload.age_days;
		frm.dashboard.clear_headline();
		frm.dashboard.set_headline(
			__("{0} kg balance of {1} kg &nbsp;|&nbsp; {2} mm ({3}\") &nbsp;|&nbsp; {4}", [
				frm.doc.current_weight, frm.doc.original_weight, frm.doc.deckle_mm, frm.doc.deckle_inch,
				age !== undefined ? __("{0} days in stock", [age]) : frm.doc.status,
			])
		);
		frm.add_custom_button(__("Refresh Balance"), () => {
			frappe.call({
				method: "corrugated_erp.corrugated_erp.doctype.paper_reel.paper_reel.refresh_balance",
				args: { reel: frm.doc.name },
				callback: () => frm.reload_doc(),
			});
		});
		frm.add_custom_button(__("Quality Test"), () => {
			frappe.new_doc("Box Quality Test", { test_type: "Incoming Paper", paper_reel: frm.doc.name });
		}, __("Create"));
		if (["In Stock", "Partially Used"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Cut into Narrow Reels"), () => {
				frappe.new_doc("Reel Slitting", { parent_reel: frm.doc.name });
			}, __("Create"));
			if (frm.doc.purchase_receipt) {
				frm.add_custom_button(__("Return to Supplier"), () => {
					frappe.confirm(__("Create a draft Purchase Return for the balance {0} kg of this reel?", [frm.doc.current_weight]), () => {
						frappe.call({
							method: "corrugated_erp.corrugated_erp.doctype.paper_reel.paper_reel.make_purchase_return",
							args: { reel: frm.doc.name },
							freeze: true,
							callback(r) {
								if (r.message) frappe.set_route("Form", "Purchase Receipt", r.message);
							},
						});
					});
				}, __("Create"));
			}
		}
		if (frm.doc.parent_reel) {
			frm.add_custom_button(__("Original Reel"), () => frappe.set_route("Form", "Paper Reel", frm.doc.parent_reel), __("View"));
		}
		frm.add_custom_button(__("Stock Ledger"), () => {
			frappe.route_options = { item_code: frm.doc.paper_item, batch_no: frm.doc.batch_no };
			frappe.set_route("query-report", "Stock Ledger");
		}, __("View"));
	},
});
})();
