(() => {
frappe.ui.form.on("Work Order", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1 || ["Completed", "Stopped", "Closed"].includes(frm.doc.status)) return;
		if (!frm.doc.box_spec) return;

		frm.add_custom_button(__("Production Entry"), () => {
			frappe.db.get_list("Production Stage", {
				filters: { is_active: 1 }, fields: ["name"], order_by: "sequence asc", limit: 1,
			}).then((stages) => {
				frappe.new_doc("Production Entry", {
					work_order: frm.doc.name,
					production_stage: stages.length ? stages[0].name : "",
					deckle_mm: frm.doc.deckle_mm,
					outs: frm.doc.outs,
				});
			});
		}, __("Corrugation"));

		frm.add_custom_button(__("Deckle Plan"), () => {
			const work_order = frm.doc.name;
			frappe.route_hooks.after_load = (plan_frm) => {
				const row = plan_frm.add_child("items");
				frappe.model.set_value(row.doctype, row.name, "work_order", work_order);
				plan_frm.refresh_field("items");
			};
			frappe.new_doc("Deckle Plan");
		}, __("Corrugation"));

		frm.add_custom_button(__("Production Entries"), () => {
			frappe.set_route("List", "Production Entry", { work_order: frm.doc.name });
		}, __("Corrugation"));
	},
});
})();
