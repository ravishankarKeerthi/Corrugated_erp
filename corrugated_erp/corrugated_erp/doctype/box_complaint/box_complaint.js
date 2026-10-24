// Copyright (c) 2026, Syvasoft Business Solutions and contributors
// For license information, please see license.txt

(() => {
frappe.ui.form.on("Box Complaint", {
	setup(frm) {
		frm.set_query("delivery_note", () => ({ filters: { customer: frm.doc.customer, docstatus: 1 } }));
		frm.set_query("sales_invoice", () => ({ filters: { customer: frm.doc.customer, docstatus: 1, is_return: 0 } }));
		frm.set_query("credit_note", () => ({ filters: { customer: frm.doc.customer, is_return: 1 } }));
		frm.set_query("box_spec", () => ({ filters: { customer: frm.doc.customer } }));
	},
	refresh(frm) {
		if (frm.doc.work_order) {
			frm.add_custom_button(__("Trace Reels & Production"), () => {
				frappe.call({
					method: "corrugated_erp.corrugated_erp.doctype.box_complaint.box_complaint.get_trace",
					args: { work_order: frm.doc.work_order },
					callback(r) {
						frm.clear_table("trace");
						(r.message || []).forEach((row) => frm.add_child("trace", row));
						frm.refresh_field("trace");
						frm.dirty();
					},
				});
			});
		}
		if (!frm.is_new() && frm.doc.status !== "Closed" && frm.doc.resolution === "Credit Note" && !frm.doc.credit_note && frm.doc.sales_invoice) {
			frm.add_custom_button(__("Credit Note"), () => {
				frappe.model.open_mapped_doc({
					method: "erpnext.accounts.doctype.sales_invoice.sales_invoice.make_sales_return",
					source_name: frm.doc.sales_invoice,
				});
			}, __("Create"));
		}
		if (frm.doc.box_spec) {
			frm.add_custom_button(__("Quality Tests"), () => frappe.set_route("List", "Box Quality Test", { box_spec: frm.doc.box_spec }), __("View"));
		}
	},
});
})();
