// Copyright (c) 2026, Syvasoft Business Solutions and contributors
// For license information, please see license.txt

frappe.query_reports["Paper Requirement Planning"] = {
	filters: [
		{ fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: frappe.defaults.get_user_default("Company") },
		{ fieldname: "to_date", label: __("Work Orders Planned Up To"), fieldtype: "Date", default: frappe.datetime.add_days(frappe.datetime.get_today(), 14) },
		{ fieldname: "only_shortage", label: __("Only Shortages"), fieldtype: "Check" },
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "shortage_kg" && data && data.shortage_kg > 0) {
			value = `<span style="color: var(--red-600); font-weight: 600">${value}</span>`;
		}
		return value;
	},
	onload(report) {
		report.page.add_inner_button(__("Material Request for Shortage"), () => {
			const rows = (report.data || []).filter((d) => d.shortage_kg > 0);
			if (!rows.length) {
				frappe.msgprint(__("No shortage to order"));
				return;
			}
			frappe.call({
				method: "corrugated_erp.api.make_paper_material_request",
				args: { rows: rows, company: report.get_filter_value("company") },
				freeze: true,
				callback(r) {
					if (r.message) frappe.set_route("Form", "Material Request", r.message);
				},
			});
		});
	},
};
