// Quotation & Sales Order: pull box prices from the latest submitted Box Costing

(() => {
["Quotation", "Sales Order"].forEach((doctype) => {
	frappe.ui.form.on(doctype, {
		refresh(frm) {
			if (frm.doc.docstatus !== 0) return;
			if (!(frm.doc.items || []).some((d) => d.box_spec)) return;
			frm.add_custom_button(__("Apply Box Costing Prices"), () => {
				const customer = frm.doc.customer || frm.doc.party_name;
				frappe.call({
					method: "corrugated_erp.api.get_box_prices",
					args: {
						items: (frm.doc.items || []).filter((d) => d.box_spec).map((d) => ({ name: d.name, box_spec: d.box_spec })),
						customer: customer,
					},
					callback(r) {
						const prices = r.message || {};
						let count = 0;
						(frm.doc.items || []).forEach((d) => {
							if (prices[d.name]) {
								// price is per box (stock UOM); a line in Kg needs price x boxes per Kg
								frappe.model.set_value(d.doctype, d.name, "rate", flt(prices[d.name].rate * (flt(d.conversion_factor) || 1), 4));
								count++;
							}
						});
						frappe.show_alert({ message: __("Updated {0} box prices", [count]), indicator: count ? "green" : "orange" });
					},
				});
			}, __("Tools"));
		},
	});
});
})();
