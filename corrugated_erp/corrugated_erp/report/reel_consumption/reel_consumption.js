// Copyright (c) 2026, Syvasoft Business Solutions and contributors
// For license information, please see license.txt

frappe.query_reports["Reel Consumption"] = {
	filters: [
		{ fieldname: "from_date", label: __("From Date"), fieldtype: "Date", reqd: 1, default: frappe.datetime.add_days(frappe.datetime.get_today(), -7) },
		{ fieldname: "to_date", label: __("To Date"), fieldtype: "Date", reqd: 1, default: frappe.datetime.get_today() },
		{ fieldname: "work_order", label: __("Work Order"), fieldtype: "Link", options: "Work Order" },
		{ fieldname: "box_spec", label: __("Box Specification"), fieldtype: "Link", options: "Box Specification" },
		{ fieldname: "workstation", label: __("Machine"), fieldtype: "Link", options: "Workstation" },
		{
			fieldname: "paper_item", label: __("Paper Item"), fieldtype: "Link", options: "Item",
			get_query: () => ({ filters: { is_kraft_paper: 1 } }),
		},
	],
};
