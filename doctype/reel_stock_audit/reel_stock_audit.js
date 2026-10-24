// Copyright (c) 2026, Syvasoft Business Solutions and contributors
// For license information, please see license.txt

(() => {
frappe.ui.form.on("Reel Stock Audit", {
	onload(frm) {
		if (frm.is_new() && !frm.doc.warehouse) {
			frappe.db.get_single_value("Corrugation Settings", "reel_warehouse").then((v) => v && frm.set_value("warehouse", v));
		}
	},
	refresh(frm) {
		if (frm.doc.docstatus !== 0) return;
		if (frappe.ui.Scanner) {
			frm.add_custom_button(__("Scan Reels with Camera"), () => {
				new frappe.ui.Scanner({
					dialog: true,
					multiple: true,
					on_scan(data) { add_scan(frm, data && data.decodedText); },
				});
			});
		}
		frm.add_custom_button(__("Type / Scanner Gun Entry"), () => {
			const d = new frappe.ui.Dialog({
				title: __("Scan reel barcodes"),
				fields: [{
					fieldname: "codes", fieldtype: "Small Text", label: __("Reel Numbers"),
					description: __("Scan with a barcode gun - one reel per line"),
				}],
				primary_action_label: __("Add"),
				primary_action(values) {
					(values.codes || "").split(/\s+/).filter(Boolean).forEach((code) => add_scan(frm, code));
					d.hide();
				},
			});
			d.show();
		});
		frm.add_custom_button(__("Compare with System"), () => frm.save());
	},
});

function add_scan(frm, code) {
	code = (code || "").trim();
	if (!code) return;
	if ((frm.doc.scans || []).some((d) => d.reel_no === code)) {
		frappe.show_alert({ message: __("{0} already scanned", [code]), indicator: "orange" });
		return;
	}
	frm.add_child("scans", { reel_no: code });
	frm.refresh_field("scans");
	frappe.show_alert({ message: __("{0} added", [code]), indicator: "green" }, 2);
}
})();
