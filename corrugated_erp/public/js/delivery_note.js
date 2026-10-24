(() => {
frappe.ui.form.on("Delivery Note Item", {
	qty: set_bundles,
	boxes_per_bundle: set_bundles,
	items_remove: (frm) => set_total_bundles(frm),
});

function set_bundles(frm, cdt, cdn) {
	const d = locals[cdt][cdn];
	const bundles = cint(d.boxes_per_bundle) ? flt(flt(d.qty) / cint(d.boxes_per_bundle), 2) : 0;
	frappe.model.set_value(cdt, cdn, "no_of_bundles", bundles);
	set_total_bundles(frm);
}

function set_total_bundles(frm) {
	frm.set_value("total_bundles", flt((frm.doc.items || []).reduce((s, d) => s + flt(d.no_of_bundles), 0), 2));
}
})();
