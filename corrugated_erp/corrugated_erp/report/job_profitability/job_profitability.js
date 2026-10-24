// Copyright (c) 2026, Syvasoft Business Solutions and contributors
// For license information, please see license.txt

frappe.query_reports["Job Profitability"] = {
	filters: [
		{ fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: frappe.defaults.get_user_default("Company") },
		{ fieldname: "from_date", label: __("Completed From"), fieldtype: "Date", default: frappe.datetime.month_start() },
		{ fieldname: "to_date", label: __("Completed To"), fieldtype: "Date", default: frappe.datetime.get_today() },
		{ fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer" },
		{ fieldname: "status", label: __("Work Order Status"), fieldtype: "Select", options: ["", "In Process", "Completed"] },
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (["margin", "margin_pct"].includes(column.fieldname) && data && data.margin < 0) {
			value = `<span style="color: var(--red-600); font-weight: 600">${value}</span>`;
		}
		return value;
	},
};
