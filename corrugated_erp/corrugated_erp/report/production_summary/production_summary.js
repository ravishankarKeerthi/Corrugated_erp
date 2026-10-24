// Copyright (c) 2026, Syvasoft Business Solutions and contributors
// For license information, please see license.txt

frappe.query_reports["Production Summary"] = {
	filters: [
		{ fieldname: "from_date", label: __("From Date"), fieldtype: "Date", reqd: 1, default: frappe.datetime.month_start() },
		{ fieldname: "to_date", label: __("To Date"), fieldtype: "Date", reqd: 1, default: frappe.datetime.get_today() },
		{
			fieldname: "group_by", label: __("Group By"), fieldtype: "Select", default: "Stage",
			options: ["Stage", "Machine", "Shift", "Operator", "Date", "Work Order"],
		},
		{ fieldname: "production_stage", label: __("Stage"), fieldtype: "Link", options: "Production Stage" },
		{ fieldname: "workstation", label: __("Machine"), fieldtype: "Link", options: "Workstation" },
		{ fieldname: "work_order", label: __("Work Order"), fieldtype: "Link", options: "Work Order" },
		{ fieldname: "shift", label: __("Shift"), fieldtype: "Select", options: ["", "General", "A", "B", "C"] },
	],
};
