// Copyright (c) 2026, Syvasoft Business Solutions and contributors
// For license information, please see license.txt

(() => {
frappe.ui.form.on("Production Entry", {
	setup(frm) {
		frm.set_query("work_order", () => ({
			filters: { docstatus: 1, status: ["in", ["Not Started", "In Process"]] },
		}));
		frm.set_query("production_stage", () => ({ filters: { is_active: 1 } }));
		frm.set_query("paper_reel", "reels", () => ({
			filters: { status: ["in", ["In Stock", "Partially Used"]] },
		}));
		frm.set_query("tooling", () => ({
			filters: { tooling_type: frm.doc.tooling_type, status: "Active" },
		}));
	},
	refresh(frm) {
		["material_transfer_entry", "manufacture_entry", "scrap_entry"].forEach((f) => {
			if (frm.doc[f]) {
				frm.add_custom_button(frm.fields_dict[f].df.label, () => frappe.set_route("Form", "Stock Entry", frm.doc[f]), __("Stock Entries"));
			}
		});
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__("Next Stage Entry"), () => next_stage(frm), __("Create"));
			frm.add_custom_button(__("Quality Test"), () => {
				frappe.new_doc("Box Quality Test", {
					test_type: frm.doc.is_final_stage ? "Final Inspection" : "In-Process",
					box_spec: frm.doc.box_spec,
					work_order: frm.doc.work_order,
					production_entry: frm.doc.name,
				});
			}, __("Create"));
		}
	},
	production_stage(frm) {
		if (!frm.doc.production_stage) return;
		frappe.db.get_value("Production Stage", frm.doc.production_stage, "default_workstation").then((r) => {
			if (r.message && r.message.default_workstation && !frm.doc.workstation) {
				frm.set_value("workstation", r.message.default_workstation);
			}
		});
	},
	work_order(frm) {
		if (!frm.doc.work_order) return;
		frappe.db.get_value("Work Order", frm.doc.work_order, ["deckle_mm", "outs"]).then((r) => {
			const v = r.message || {};
			if (v.deckle_mm && !frm.doc.deckle_mm) frm.set_value("deckle_mm", v.deckle_mm);
			if (v.outs && !frm.doc.outs) frm.set_value("outs", v.outs);
		});
	},
	start_time: calc_time,
	end_time: calc_time,
	output_qty(frm) {
		calc_time(frm);
		calc_labour(frm);
		const factor = frm.doc.output_in === "Sheets" ? cint(frm.doc.ups) || 1 : 1;
		frm.set_value("box_equivalent", flt(frm.doc.output_qty) * factor);
	},
	piece_rate: calc_labour,
	piece_rate_basis: calc_labour,
});

frappe.ui.form.on("Production Entry Downtime", {
	from_time: downtime_minutes,
	to_time: downtime_minutes,
	minutes(frm) { calc_time(frm); },
	downtime_remove(frm) { calc_time(frm); },
});

frappe.ui.form.on("Production Entry Material", {
	item_code(frm, cdt, cdn) {
		const d = locals[cdt][cdn];
		if (d.item_code && !d.s_warehouse) {
			frappe.db.get_value("Item Default", { parent: d.item_code, company: frm.doc.company }, "default_warehouse").then((r) => {
				const wh = r.message && r.message.default_warehouse;
				if (wh) frappe.model.set_value(cdt, cdn, "s_warehouse", wh);
			});
		}
	},
});

function downtime_minutes(frm, cdt, cdn) {
	const d = locals[cdt][cdn];
	if (d.from_time && d.to_time) {
		let mins = moment(d.to_time, "HH:mm:ss").diff(moment(d.from_time, "HH:mm:ss"), "minutes");
		if (mins < 0) mins += 24 * 60;
		frappe.model.set_value(cdt, cdn, "minutes", mins);
	}
}

function calc_labour(frm) {
	if (!flt(frm.doc.piece_rate)) return;
	const per = frm.doc.piece_rate_basis === "Per Nos" ? 1 : 1000;
	frm.set_value("labour_amount", flt(flt(frm.doc.output_qty) / per * flt(frm.doc.piece_rate), 2));
}

frappe.ui.form.on("Production Entry Reel", {
	paper_reel(frm, cdt, cdn) {
		const d = locals[cdt][cdn];
		if (!d.paper_reel) return;
		frappe.call({
			method: "corrugated_erp.corrugated_erp.doctype.production_entry.production_entry.get_reel_details",
			args: { reel: d.paper_reel },
			callback(r) {
				const v = r.message || {};
				frappe.model.set_value(cdt, cdn, {
					paper_item: v.paper_item,
					opening_weight: v.current_weight,
					batch_no: v.batch_no,
					warehouse: v.warehouse,
					deckle_mm: v.deckle_mm,
				});
				if (frm.doc.deckle_mm && v.deckle_mm && flt(v.deckle_mm) !== flt(frm.doc.deckle_mm)) {
					frappe.show_alert({ message: __("Reel deckle {0} mm differs from run deckle {1} mm", [v.deckle_mm, frm.doc.deckle_mm]), indicator: "orange" });
				}
			},
		});
	},
	closing_weight(frm, cdt, cdn) {
		const d = locals[cdt][cdn];
		if (flt(d.closing_weight) > flt(d.opening_weight)) {
			frappe.msgprint(__("Balance cannot be more than the opening weight {0} kg", [d.opening_weight]));
			frappe.model.set_value(cdt, cdn, "closing_weight", d.opening_weight);
			return;
		}
		frappe.model.set_value(cdt, cdn, "consumed_kg", flt(flt(d.opening_weight) - flt(d.closing_weight), 3));
		frm.set_value("total_reel_consumed_kg", (frm.doc.reels || []).reduce((s, r) => s + flt(r.consumed_kg), 0));
	},
	reels_remove(frm) {
		frm.set_value("total_reel_consumed_kg", (frm.doc.reels || []).reduce((s, r) => s + flt(r.consumed_kg), 0));
	},
});

frappe.ui.form.on("Production Entry Waste", {
	qty_kg: set_waste_total,
	waste_remove: set_waste_total,
});

function set_waste_total(frm) {
	frm.set_value("total_waste_kg", (frm.doc.waste || []).reduce((s, r) => s + flt(r.qty_kg), 0));
}

function calc_time(frm) {
	const down = (frm.doc.downtime || []).reduce((a, d) => a + flt(d.minutes), 0);
	frm.set_value("total_downtime_min", down);
	if (frm.doc.start_time && frm.doc.end_time) {
		const hrs = moment(frm.doc.end_time).diff(moment(frm.doc.start_time), "minutes") / 60;
		const net = Math.max(hrs - down / 60, 0);
		frm.set_value("duration_hrs", flt(hrs, 2));
		frm.set_value("net_run_hrs", flt(net, 2));
		frm.set_value("output_per_hour", net > 0 ? flt(flt(frm.doc.output_qty) / net, 1) : 0);
		frm.set_value("availability_pct", hrs > 0 ? flt(net / hrs * 100, 1) : 0);
	}
}

function next_stage(frm) {
	frappe.db.get_value("Production Stage", frm.doc.production_stage, "sequence").then((r) => {
		const seq = (r.message || {}).sequence || 0;
		frappe.db.get_list("Production Stage", {
			filters: { is_active: 1, sequence: [">", seq] },
			fields: ["name", "output_in"],
			order_by: "sequence asc",
			limit: 1,
		}).then((stages) => {
			const next = stages[0] || {};
			const carry = next.output_in === frm.doc.output_in ? frm.doc.output_qty : frm.doc.box_equivalent;
			frappe.new_doc("Production Entry", {
				work_order: frm.doc.work_order,
				production_stage: next.name || "",
				input_qty: carry,
				shift: frm.doc.shift,
			});
		});
	});
}
})();
