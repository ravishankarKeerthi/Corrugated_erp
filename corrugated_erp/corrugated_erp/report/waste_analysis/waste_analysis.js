// Copyright (c) 2026, Syvasoft Business Solutions and contributors
// For license information, please see license.txt

frappe.query_reports["Waste Analysis"] = {
	filters: [
		{ fieldname: "from_date", label: __("From Date"), fieldtype: "Date", reqd: 1, default: frappe.datetime.month_start() },
		{ fieldname: "to_date", label: __("To Date"), fieldtype: "Date", reqd: 1, default: frappe.datetime.get_today() },
		{ fieldname: "production_stage", label: __("Stage"), fieldtype: "Link", options: "Production Stage" },
		{ fieldname: "workstation", label: __("Machine"), fieldtype: "Link", options: "Workstation" },
	],
};
