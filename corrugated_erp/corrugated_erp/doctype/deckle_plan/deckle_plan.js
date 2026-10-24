// Copyright (c) 2026, Syvasoft Business Solutions and contributors
// For license information, please see license.txt

(() => {
frappe.ui.form.on("Deckle Plan", {
	setup(frm) {
		frm.set_query("work_order", "items", () => ({
			filters: { docstatus: 1, status: ["in", ["Not Started", "In Process"]] },
		}));
	},
	refresh(frm) {
		frm.add_custom_button(__("Suggest Best Deckle"), () => suggest(frm));
		if (!frm.is_new() && frm.doc.status === "Planned") {
			frm.add_custom_button(__("Production Entry"), () => {
				const first = (frm.doc.items || [])[0];
				frappe.new_doc("Production Entry", {
					work_order: first && first.work_order,
					production_stage: "Corrugation",
					deckle_mm: frm.doc.deckle_mm,
					outs: first && first.outs,
				});
			}, __("Create"));
		}
	},
	deckle_mm(frm) { calc(frm); },
});

frappe.ui.form.on("Deckle Plan Item", {
	outs: (frm) => calc(frm),
	sheet_width_mm: (frm) => calc(frm),
	items_remove: (frm) => calc(frm),
});

function calc(frm) {
	let used = 0;
	let running = 0;
	(frm.doc.items || []).forEach((d) => {
		d.outs = Math.max(1, cint(d.outs));
		d.used_width_mm = flt(flt(d.sheet_width_mm) * d.outs, 1);
		d.cuts_required = Math.ceil(flt(d.qty) / d.outs);
		d.running_metres = flt((d.cuts_required * flt(d.sheet_length_mm)) / 1000, 1);
		used += d.used_width_mm;
		running = Math.max(running, d.running_metres);
	});
	frm.doc.total_used_width_mm = flt(used, 1);
	frm.doc.total_running_metres = flt(running, 1);
	frm.doc.deckle_inch = flt(frm.doc.deckle_mm / 25.4, 2);
	frm.doc.trim_mm = frm.doc.deckle_mm ? flt(frm.doc.deckle_mm - used, 1) : 0;
	frm.doc.trim_pct = frm.doc.deckle_mm ? flt((frm.doc.trim_mm / frm.doc.deckle_mm) * 100, 2) : 0;
	frm.refresh_fields();
}

function suggest(frm) {
	if (!(frm.doc.items || []).length) {
		frappe.msgprint(__("Add work orders first"));
		return;
	}
	frappe.call({
		method: "corrugated_erp.corrugated_erp.doctype.deckle_plan.deckle_plan.suggest",
		args: { doc: frm.doc },
		callback(r) {
			const options = r.message || [];
			if (!options.length) {
				frappe.msgprint(__("No standard deckle fits these widths. Reduce outs or add a wider deckle in Corrugation Settings."));
				return;
			}
			const d = new frappe.ui.Dialog({
				title: __("Deckle options (least trim first)"),
				fields: [{
					fieldname: "options", fieldtype: "Table", cannot_add_rows: true, in_place_edit: false,
					data: options.map((o) => ({ ...o, outs_text: o.outs.join(" + ") })),
					fields: [
						{ fieldname: "deckle_mm", label: __("Deckle (mm)"), fieldtype: "Float", in_list_view: 1, read_only: 1 },
						{ fieldname: "deckle_inch", label: __("Inch"), fieldtype: "Float", in_list_view: 1, read_only: 1 },
						{ fieldname: "outs_text", label: __("Outs"), fieldtype: "Data", in_list_view: 1, read_only: 1 },
						{ fieldname: "used_width_mm", label: __("Used (mm)"), fieldtype: "Float", in_list_view: 1, read_only: 1 },
						{ fieldname: "trim_pct", label: __("Trim %"), fieldtype: "Percent", in_list_view: 1, read_only: 1 },
					],
				}],
				primary_action_label: __("Apply Selected"),
				primary_action() {
					const picked = d.fields_dict.options.grid.get_selected_children()[0] || d.fields_dict.options.df.data[0];
					frm.set_value("deckle_mm", picked.deckle_mm);
					if ((frm.doc.items || []).length === 1) {
						frm.doc.items[0].outs = picked.outs[0];
					}
					calc(frm);
					d.hide();
				},
			});
			d.show();
		},
	});
}
})();
