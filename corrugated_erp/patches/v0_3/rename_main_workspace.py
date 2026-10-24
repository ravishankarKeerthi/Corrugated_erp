"""0.3: the main workspace is now 'Corrugation' ('Corrugated ERP' is the app tile and icon group)."""

import frappe


def execute():
	if frappe.db.exists("Workspace", "Corrugated ERP") and frappe.db.exists("Workspace", "Corrugation"):
		frappe.delete_doc("Workspace", "Corrugated ERP", force=True, ignore_permissions=True)
	for doctype in ("Workspace Sidebar", "Sidebar"):
		if frappe.db.exists("DocType", doctype) and frappe.db.exists(doctype, "Corrugated ERP"):
			frappe.delete_doc(doctype, "Corrugated ERP", force=True, ignore_permissions=True)
