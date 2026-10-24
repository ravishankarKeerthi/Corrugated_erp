// Copyright (c) 2026, Syvasoft Business Solutions and contributors
// For license information, please see license.txt
//
// Shop Floor Entry: one simple screen for machine operators on a phone or tablet.
// Pick (or scan) the Work Order, choose the stage, scan reels and type their balance
// weight, enter output, waste and stoppages, then Save. It creates a Production Entry.

frappe.pages["box-shop-floor"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Shop Floor Entry"), single_column: true });
	new ShopFloor(page);
};

const SF_API = "corrugated_erp.shop_floor.";
const WASTE_TYPES = ["Deckle Trim", "Reject Sheets", "Reject Boxes", "Reel End / Core", "Print Waste", "Other"];
const DOWN_REASONS = [
	"Breakdown - Mechanical", "Breakdown - Electrical", "Power Cut", "No Paper / Material", "Waiting for Order",
	"Setup / Changeover", "Gum / Steam Problem", "Operator Not Available", "Quality Hold", "Planned Maintenance", "Other",
];

class ShopFloor {
	constructor(page) {
		this.page = page;
		this.reels = [];
		this.downtime = [];
		this.started_at = frappe.datetime.now_datetime();
		this.wo = null;
		this.render();
	}

	render() {
		const $body = $(this.page.body).empty().addClass("sf-body");
		$body.append(`
			<style>
				.sf-body { max-width: 720px; margin: 0 auto; }
				.sf-card { background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 10px; padding: 14px; margin-bottom: 12px; }
				.sf-card h5 { margin: 0 0 10px; font-weight: 600; }
				.sf-info { font-size: 13px; color: var(--text-muted); line-height: 1.6; }
				.sf-stages { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
				.sf-stage { padding: 6px 10px; border-radius: 16px; border: 1px solid var(--border-color); cursor: pointer; font-size: 13px; }
				.sf-stage.active { background: var(--primary); color: #fff; border-color: var(--primary); }
				.sf-stage .n { opacity: .75; font-size: 11px; margin-left: 4px; }
				.sf-row { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
				.sf-row input, .sf-row select { flex: 1; min-height: 40px; font-size: 16px; }
				.sf-reel { border-bottom: 1px dashed var(--border-color); padding: 6px 0; }
				.sf-big { min-height: 48px; font-size: 18px; width: 100%; }
				.sf-warn { color: var(--red-600); font-weight: 600; }
			</style>
			<div class="sf-card sf-wo"></div>
			<div class="sf-card sf-main" style="display:none"></div>
		`);
		this.$wo = $body.find(".sf-wo");
		this.$main = $body.find(".sf-main");
		this.wo_field = frappe.ui.form.make_control({
			parent: this.$wo,
			df: {
				fieldtype: "Link", options: "Work Order", label: __("Work Order (type or scan)"), fieldname: "work_order",
				get_query: () => ({ filters: { docstatus: 1, status: ["in", ["Not Started", "In Process"]] } }),
				change: () => this.load_wo(this.wo_field.get_value()),
			},
			render_input: true,
		});
		this.$wo.append(`<div class="sf-info sf-wo-info"></div>`);
	}

	load_wo(name) {
		if (!name || (this.wo && this.wo.work_order.name === name)) return;
		frappe.call({ method: SF_API + "get_work_order", args: { work_order: name } }).then((r) => {
			this.wo = r.message;
			const w = this.wo.work_order, s = this.wo.spec || {};
			const art = s.printing_type && s.printing_type !== "None" && s.artwork_status !== "Approved"
				? `<div class="sf-warn">${__("Artwork not approved - printing is blocked")}</div>` : "";
			this.$wo.find(".sf-wo-info").html(`
				<div><b>${frappe.utils.escape_html(w.item_name || "")}</b> &middot; ${frappe.utils.escape_html(s.customer || "")}</div>
				<div>${__("Order")}: ${w.qty} &nbsp; ${__("Finished")}: ${w.produced_qty}</div>
				<div>${s.length_mm || ""} x ${s.width_mm || ""} x ${s.height_mm || ""} mm, ${s.ply || ""} ply &nbsp;|&nbsp;
					${__("Sheet")} ${s.sheet_length_mm || ""} x ${s.sheet_width_mm || ""} mm${cint(s.ups_per_sheet) > 1 ? ", " + s.ups_per_sheet + " " + __("ups") : ""}
					&nbsp;|&nbsp; ${__("Deckle")} ${w.deckle_mm || "-"} mm, ${w.outs || "-"} ${__("outs")}</div>
				${art}
				<div class="sf-stages"></div>`);
			const $st = this.$wo.find(".sf-stages");
			this.wo.stages.forEach((st) => {
				$(`<span class="sf-stage" data-stage="${frappe.utils.escape_html(st.name)}">${frappe.utils.escape_html(st.name)}<span class="n">${st.done || ""}</span></span>`)
					.appendTo($st)
					.on("click", () => this.set_stage(st.name));
			});
			this.set_stage(this.wo.next_stage);
		});
	}

	set_stage(name) {
		this.stage = (this.wo.stages || []).find((s) => s.name === name);
		this.$wo.find(".sf-stage").removeClass("active");
		this.$wo.find(`.sf-stage[data-stage="${CSS.escape(name || "")}"]`).addClass("active");
		this.reels = [];
		this.downtime = [];
		this.render_main();
	}

	render_main() {
		const st = this.stage;
		if (!st) return;
		this.$main.show().empty();
		this.$main.append(`<h5>${frappe.utils.escape_html(st.name)} &middot; ${__("output in")} ${__(st.output_in || "Boxes")}</h5>`);
		this.fg = new frappe.ui.FieldGroup({
			parent: this.$main,
			fields: [
				{ fieldtype: "Link", options: "Workstation", fieldname: "workstation", label: __("Machine"), default: st.default_workstation },
				{ fieldtype: "Link", options: "Employee", fieldname: "operator", label: __("Operator") },
				{ fieldtype: "Column Break" },
				{ fieldtype: "Select", fieldname: "shift", label: __("Shift"), options: ["General", "A", "B", "C"], default: "General" },
				{ fieldtype: "Datetime", fieldname: "start_time", label: __("Started At"), default: this.started_at },
				{ fieldtype: "Section Break" },
				{ fieldtype: "Float", fieldname: "output_qty", label: __("Good Output ({0})", [__(st.output_in || "Boxes")]), reqd: 1 },
				{ fieldtype: "Column Break" },
				{ fieldtype: "Float", fieldname: "rejected_qty", label: __("Rejected") },
			],
		});
		this.fg.make();

		if (cint(st.consumes_reels)) {
			const $r = $(`<div class="sf-card"><h5>${__("Reels")}</h5>
				<div class="sf-row"><input class="form-control sf-scan" placeholder="${__("Scan or type reel no, then Enter")}"></div>
				<div class="sf-reels"></div></div>`).appendTo(this.$main);
			$r.find(".sf-scan").on("keydown", (e) => {
				if (e.key === "Enter") {
					e.preventDefault();
					this.add_reel($(e.target).val());
					$(e.target).val("");
				}
			});
			this.$reels = $r.find(".sf-reels");
		}

		const $w = $(`<div class="sf-card"><h5>${__("Waste (kg)")}</h5></div>`).appendTo(this.$main);
		WASTE_TYPES.slice(0, 4).forEach((t) => {
			$w.append(`<div class="sf-row"><label style="flex:1">${__(t)}</label><input type="number" step="0.1" inputmode="decimal" class="form-control sf-waste" data-type="${t}"></div>`);
		});

		const $d = $(`<div class="sf-card"><h5>${__("Stoppages")}</h5>
			<div class="sf-row"><select class="form-control sf-dreason">${DOWN_REASONS.map((r) => `<option>${__(r)}</option>`).join("")}</select>
			<input type="number" inputmode="numeric" class="form-control sf-dmin" placeholder="${__("Minutes")}" style="max-width:110px">
			<button class="btn btn-default sf-dadd">${__("Add")}</button></div><div class="sf-dlist sf-info"></div></div>`).appendTo(this.$main);
		$d.find(".sf-dadd").on("click", () => {
			const mins = flt($d.find(".sf-dmin").val());
			if (!mins) return;
			this.downtime.push({ reason: DOWN_REASONS[$d.find(".sf-dreason")[0].selectedIndex], minutes: mins });
			$d.find(".sf-dmin").val("");
			$d.find(".sf-dlist").html(this.downtime.map((x) => `${__(x.reason)}: ${x.minutes} ${__("min")}`).join("<br>"));
		});

		const $btn = $(`<div class="sf-card">
			<label class="sf-info"><input type="checkbox" class="sf-submit" checked> ${__("Submit now (books stock)")}</label>
			<button class="btn btn-primary sf-big sf-save" style="margin-top:8px">${__("Save Entry")}</button></div>`).appendTo(this.$main);
		$btn.find(".sf-save").on("click", () => this.save($btn.find(".sf-submit").is(":checked")));
	}

	add_reel(no) {
		no = (no || "").trim();
		if (!no || this.reels.find((r) => r.paper_reel === no)) return;
		frappe.call({ method: SF_API + "get_reel", args: { reel: no } }).then((r) => {
			const reel = r.message;
			const row = { paper_reel: reel.name, opening: flt(reel.current_weight), closing_weight: null };
			this.reels.push(row);
			const $row = $(`<div class="sf-reel">
				<div><b>${frappe.utils.escape_html(reel.name)}</b> &middot; ${reel.bf || ""} BF / ${reel.gsm || ""} GSM &middot; ${reel.deckle_mm} mm &middot;
					${__("balance")} ${reel.current_weight} kg</div>
				<div class="sf-row"><input type="number" step="0.1" inputmode="decimal" class="form-control" placeholder="${__("Balance weight left on reel (kg)")}">
				<button class="btn btn-default btn-xs">${__("Used fully")}</button></div></div>`).appendTo(this.$reels);
			$row.find("input").on("change", (e) => (row.closing_weight = flt($(e.target).val())));
			$row.find("button").on("click", () => { row.closing_weight = 0; $row.find("input").val(0); });
		});
	}

	save(submit) {
		const v = this.fg.get_values();
		if (!v) return;
		if (cint(this.stage.consumes_reels)) {
			if (!this.reels.length) return frappe.msgprint(__("Scan the reels used"));
			if (this.reels.some((r) => r.closing_weight === null)) return frappe.msgprint(__("Enter the balance weight for every reel (0 if fully used)"));
		}
		const waste = [];
		this.$main.find(".sf-waste").each((_, el) => {
			const q = flt($(el).val());
			if (q > 0) waste.push({ waste_type: $(el).data("type"), qty_kg: q });
		});
		frappe.call({
			method: SF_API + "submit_entry",
			freeze: true,
			args: {
				data: {
					...v,
					work_order: this.wo.work_order.name,
					production_stage: this.stage.name,
					end_time: frappe.datetime.now_datetime(),
					reels: this.reels.map((r) => ({ paper_reel: r.paper_reel, closing_weight: r.closing_weight })),
					waste: waste,
					downtime: this.downtime,
					submit: submit ? 1 : 0,
				},
			},
		}).then((r) => {
			const m = r.message;
			frappe.msgprint({
				title: __("Saved"),
				indicator: "green",
				message: __("Production Entry {0} {1}", [
					`<a href="/app/production-entry/${encodeURIComponent(m.name)}">${frappe.utils.escape_html(m.name)}</a>`,
					m.docstatus === 1 ? __("submitted") : __("saved as draft"),
				]),
			});
			this.started_at = frappe.datetime.now_datetime();
			const wo = this.wo.work_order.name;
			this.wo = null;
			this.load_wo(wo);
		});
	}
}
