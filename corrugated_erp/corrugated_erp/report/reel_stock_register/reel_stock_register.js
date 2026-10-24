// Copyright (c) 2026, Syvasoft Business Solutions and contributors
// For license information, please see license.txt

frappe.query_reports["Reel Stock Register"] = {
	filters: [
		{ fieldname: "warehouse", label: __("Warehouse"), fieldtype: "Link", options: "Warehouse" },
		{
			fieldname: "paper_item", label: __("Paper Item"), fieldtype: "Link", options: "Item",
			get_query: () => ({ filters: { is_kraft_paper: 1 } }),
		},
		{ fieldname: "gsm", label: __("GSM"), fieldtype: "Float" },
		{ fieldname: "deckle_from", label: __("Deckle From (mm)"), fieldtype: "Float" },
		{ fieldname: "deckle_to", label: __("Deckle To (mm)"), fieldtype: "Float" },
		{ fieldname: "supplier", label: __("Supplier"), fieldtype: "Link", options: "Supplier" },
		{
			fieldname: "status", label: __("Status"), fieldtype: "MultiSelectList",
			get_data: () => ["In Stock", "Partially Used", "Consumed", "Pending Receipt", "Damaged", "Returned"]
				.map((s) => ({ value: s, description: "" })),
			default: ["In Stock", "Partially Used"],
		},
		{ fieldname: "min_age_days", label: __("Older Than (days)"), fieldtype: "Int" },
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "age_days" && data && data.age_days > 90) {
			value = `<span style="color: var(--red-600)">${value}</span>`;
		}
		return value;
	},
};
