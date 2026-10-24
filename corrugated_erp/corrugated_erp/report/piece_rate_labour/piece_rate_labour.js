// Copyright (c) 2026, Syvasoft Business Solutions and contributors
// For license information, please see license.txt

frappe.query_reports["Piece Rate Labour"] = {
	filters: [
		{ fieldname: "from_date", label: __("From Date"), fieldtype: "Date", reqd: 1, default: frappe.datetime.month_start() },
		{ fieldname: "to_date", label: __("To Date"), fieldtype: "Date", reqd: 1, default: frappe.datetime.get_today() },
		{ fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company" },
		{ fieldname: "contractor", label: __("Contractor"), fieldtype: "Link", options: "Supplier" },
		{ fieldname: "operator", label: __("Operator"), fieldtype: "Link", options: "Employee" },
		{ fieldname: "production_stage", label: __("Stage"), fieldtype: "Link", options: "Production Stage" },
		{ fieldname: "show_entries", label: __("Show Each Entry"), fieldtype: "Check" },
	],
};
