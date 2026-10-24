// Copyright (c) 2026, Syvasoft Business Solutions and contributors
// For license information, please see license.txt

(() => {
const COSTING_INPUTS = [
	"waste_pct", "conversion_rate_per_kg", "print_rate_per_colour_per_1000", "plate_cost", "plate_amortise_qty",
	"die_cost", "die_amortise_qty", "stitch_rate", "gum_rate", "other_cost_per_box", "overhead_pct",
	"freight_per_box", "margin_pct", "quantity", "quoted_price_per_box", "no_of_colours", "stitches_per_box",
	"quoted_price_per_kg", "pricing_basis",
];

const costing_events = {
	setup(frm) {
		frm.set_query("box_spec", () => ({ filters: { status: ["!=", "Obsolete"] } }));
		frm.set_query("selling_price_list", () => ({ filters: { selling: 1 } }));
	},
	refresh(frm) {
		if (frm.doc.docstatus === 0 && frm.doc.box_spec) {
			frm.add_custom_button(__("Reload from Specification"), () => {
				frm.clear_table("papers");
				frm.save();
			});
		}
		if (frm.doc.approval_status === "Pending Approval") {
			frm.set_intro(
				__("Margin {0}% is below the minimum {1}%. Only the margin approver can submit this costing.", [
					frm.doc.achieved_margin_pct, frm.doc.min_margin_pct,
				]),
				"orange"
			);
		} else if (frm.doc.approval_status === "Approved" && frm.doc.approved_by) {
			frm.set_intro(__("Low margin approved by {0}", [frm.doc.approved_by]), "green");
		}
		if (frm.doc.total_cost_per_box) {
			frm.dashboard.clear_headline();
			frm.dashboard.set_headline(
				__("Cost {0} &nbsp;|&nbsp; Price {1} per box &nbsp;|&nbsp; {2} per kg &nbsp;|&nbsp; Margin {3}%", [
					format_currency(frm.doc.total_cost_per_box, null, 4),
					format_currency(frm.doc.final_price_per_box, null, 4),
					format_currency(frm.doc.price_per_kg),
					frm.doc.achieved_margin_pct,
				])
			);
		}
	},
	box_spec(frm) {
		if (frm.doc.box_spec) {
			frm.clear_table("papers");
			frm.refresh_field("papers");
		}
	},
};
COSTING_INPUTS.forEach((f) => (costing_events[f] = schedule_costing));
frappe.ui.form.on("Box Costing", costing_events);

frappe.ui.form.on("Box Costing Paper", {
	rate: schedule_costing,
	weight_kg: schedule_costing,
	papers_remove: schedule_costing,
});

function schedule_costing(frm) {
	if (frm.doc.docstatus !== 0 || !(frm.doc.papers || []).length) return;
	clearTimeout(frm.__bc_timer);
	frm.__bc_timer = setTimeout(() => {
		frappe.call({
			method: "corrugated_erp.corrugated_erp.doctype.box_costing.box_costing.get_costing_values",
			args: { doc: frm.doc },
			callback(r) {
				if (!r.message) return;
				const papers = r.message.papers || [];
				delete r.message.papers;
				Object.assign(frm.doc, r.message);
				papers.forEach((p) => {
					const row = (frm.doc.papers || []).find((d) => d.idx === p.idx);
					if (row) row.amount = p.amount;
				});
				frm.refresh_fields();
				frm.dirty();
			},
		});
	}, 400);
}
})();
