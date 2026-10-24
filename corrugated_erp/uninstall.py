import frappe

from corrugated_erp.install import get_custom_fields


def before_uninstall():
	for doctype, fields in get_custom_fields().items():
		for field in fields:
			name = frappe.db.get_value("Custom Field", {"dt": doctype, "fieldname": field["fieldname"]})
			if name:
				frappe.delete_doc("Custom Field", name, ignore_permissions=True)
