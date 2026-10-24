(() => {
frappe.ui.form.on("Item", {
	is_kraft_paper(frm) {
		if (frm.doc.is_kraft_paper) {
			frm.set_value("has_batch_no", 1);
			frm.set_value("is_stock_item", 1);
			if (!frm.doc.stock_uom || frm.doc.stock_uom === "Nos") frm.set_value("stock_uom", "Kg");
			frappe.db.get_single_value("Corrugation Settings", "paper_item_group").then((g) => g && frm.set_value("item_group", g));
		}
	},
	refresh(frm) {
		if (frm.doc.box_spec) {
			frm.add_custom_button(__("Box Specification"), () => frappe.set_route("Form", "Box Specification", frm.doc.box_spec), __("View"));
		}
		if (frm.doc.is_kraft_paper && !frm.is_new()) {
			frm.add_custom_button(__("Reels"), () => frappe.set_route("List", "Paper Reel", { paper_item: frm.doc.name }), __("View"));
		}
	},
});
})();
