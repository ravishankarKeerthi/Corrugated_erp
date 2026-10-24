// Copyright (c) 2026, Syvasoft Business Solutions and contributors
// For license information, please see license.txt

(() => {
const SPEC_METHOD = "corrugated_erp.corrugated_erp.doctype.box_specification.box_specification.";

frappe.ui.form.on("Box Specification", {
	setup(frm) {
		frm.set_query("paper_item", "layers", () => ({ filters: { is_kraft_paper: 1, disabled: 0 } }));
		frm.set_query("die_tooling", () => ({ filters: { tooling_type: "Die", status: ["!=", "Scrapped"] } }));
		frm.set_query("plate_tooling", () => ({ filters: { tooling_type: "Printing Plate", status: ["!=", "Scrapped"] } }));
	},

	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(frm.doc.item_code ? __("Update BOM") : __("Create Item & BOM"), () => {
			frappe.call({
				method: SPEC_METHOD + "create_item_and_bom",
				args: { box_spec: frm.doc.name },
				freeze: true,
				freeze_message: __("Creating item and BOM..."),
				callback(r) {
					if (r.message) {
						frappe.show_alert({ message: __("BOM {0} created", [r.message.bom]), indicator: "green" });
						frm.reload_doc();
					}
				},
			});
		}, __("Create"));

		frm.add_custom_button(__("Box Costing"), () => {
			frappe.call({
				method: "corrugated_erp.corrugated_erp.doctype.box_costing.box_costing.make_costing",
				args: { box_spec: frm.doc.name },
				callback(r) {
					if (r.message) {
						const doc = frappe.model.sync(r.message)[0];
						frappe.set_route("Form", doc.doctype, doc.name);
					}
				},
			});
		}, __("Create"));

		frm.add_custom_button(__("Deckle Options"), () => show_deckle_options(frm), __("View"));
		if (frm.doc.item_code) {
			frm.add_custom_button(__("Box Item"), () => frappe.set_route("Form", "Item", frm.doc.item_code), __("View"));
		}
		if (frm.doc.latest_costing) {
			frm.add_custom_button(__("Latest Costing"), () => frappe.set_route("Form", "Box Costing", frm.doc.latest_costing), __("View"));
		}
		frm.dashboard.clear_headline();
		if (frm.doc.printing_type && frm.doc.printing_type !== "None" && frm.doc.artwork_status !== "Approved") {
			frm.dashboard.add_indicator(__("Artwork: {0}", [__(frm.doc.artwork_status || "Pending")]), "orange");
		}
		if (cint(frm.doc.revision) > 1) {
			frm.dashboard.add_indicator(__("Revision {0}", [frm.doc.revision]), "blue");
		}
		if (frm.doc.box_weight_g) {
			frm.dashboard.set_headline(
				__("Sheet {0} x {1} mm &nbsp;|&nbsp; Board {2} GSM &nbsp;|&nbsp; Box {3} g &nbsp;|&nbsp; BS {4} kg/cm²", [
					frm.doc.sheet_length_mm, frm.doc.sheet_width_mm, frm.doc.board_gsm, frm.doc.box_weight_g, frm.doc.theoretical_bs,
				])
			);
		}
	},

	ply(frm) { rebuild_layers(frm); },
	flute_1(frm) { rebuild_layers(frm); },
	flute_2(frm) { rebuild_layers(frm); },
	flute_3(frm) { rebuild_layers(frm); },
	box_style: schedule_recalc,
	dimension_basis: schedule_recalc,
	length_mm: schedule_recalc,
	width_mm: schedule_recalc,
	height_mm: schedule_recalc,
	manual_sheet_length_mm: schedule_recalc,
	manual_sheet_width_mm: schedule_recalc,
	caliper_override_mm: schedule_recalc,
	ect_kn_per_m: schedule_recalc,
	ups_per_sheet: schedule_recalc,
	artwork_status(frm) {
		if (frm.doc.artwork_status === "Approved" && !frm.doc.artwork_approved_on) {
			frm.set_value("artwork_approved_on", frappe.datetime.get_today());
		}
	},
});

frappe.ui.form.on("Box Spec Layer", {
	gsm: schedule_recalc,
	bf: schedule_recalc,
	take_up_factor: schedule_recalc,
	paper_item(frm) { setTimeout(() => schedule_recalc(frm), 300); },
	flute_type(frm) { setTimeout(() => schedule_recalc(frm), 300); },
	layers_remove: schedule_recalc,
});

function rebuild_layers(frm) {
	const ply = cint(frm.doc.ply);
	const needed = ply === 7 ? 3 : ply === 5 ? 2 : 1;
	const flutes = [frm.doc.flute_1, frm.doc.flute_2, frm.doc.flute_3].slice(0, needed);
	if (flutes.some((f) => !f)) return;

	// keep paper choices for layers with the same name
	const old = {};
	(frm.doc.layers || []).forEach((d) => (old[d.layer_name] = d));

	frappe.call({
		method: SPEC_METHOD + "get_layer_template",
		args: { ply: frm.doc.ply, flute_1: flutes[0], flute_2: flutes[1], flute_3: flutes[2] },
		callback(r) {
			if (!r.message) return;
			frm.clear_table("layers");
			r.message.forEach((row) => {
				const prev = old[row.layer_name] || {};
				const child = frm.add_child("layers", row);
				["paper_item", "gsm", "bf", "shade"].forEach((f) => prev[f] && (child[f] = prev[f]));
			});
			frm.refresh_field("layers");
			schedule_recalc(frm);
		},
	});
}

function schedule_recalc(frm) {
	clearTimeout(frm.__sc_timer);
	frm.__sc_timer = setTimeout(() => recalc(frm), 400);
}

function recalc(frm) {
	if (!frm.doc.box_style || !(frm.doc.layers || []).length) return;
	frappe.call({
		method: SPEC_METHOD + "get_calculated",
		args: { doc: frm.doc },
		callback(r) {
			if (!r.message || !r.message.fields) return;
			Object.assign(frm.doc, r.message.fields);
			(r.message.layers || []).forEach((l) => {
				const row = (frm.doc.layers || []).find((d) => d.idx === l.idx);
				if (row) Object.assign(row, l);
			});
			frm.refresh_fields();
			frm.dirty();
		},
	});
}

function show_deckle_options(frm) {
	if (!frm.doc.sheet_width_mm) {
		frappe.msgprint(__("Save the specification first to calculate the sheet width"));
		return;
	}
	frappe.call({
		method: SPEC_METHOD + "get_deckle_options",
		args: { sheet_width_mm: frm.doc.sheet_width_mm },
		callback(r) {
			const rows = (r.message || [])
				.map((o) => `<tr><td>${o.deckle_mm}</td><td>${o.deckle_inch}"</td><td>${o.outs[0]}</td>
					<td>${o.used_width_mm}</td><td>${o.trim_mm}</td><td><b>${o.trim_pct}%</b></td></tr>`)
				.join("");
			frappe.msgprint({
				title: __("Deckle options for sheet width {0} mm", [frm.doc.sheet_width_mm]),
				message: rows
					? `<table class="table table-bordered table-sm"><thead><tr><th>${__("Deckle mm")}</th><th>${__("Inch")}</th>
						<th>${__("Outs")}</th><th>${__("Used mm")}</th><th>${__("Trim mm")}</th><th>${__("Trim %")}</th></tr></thead>
						<tbody>${rows}</tbody></table>`
					: __("No standard deckle fits. Add deckles in Corrugation Settings."),
				wide: true,
			});
		},
	});
}
})();
