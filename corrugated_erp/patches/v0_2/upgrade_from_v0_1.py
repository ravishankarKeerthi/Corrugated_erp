"""Fill the fields added in 0.2 for records created with 0.1."""

import frappe


def execute():
	frappe.db.sql("update `tabBox Specification` set ups_per_sheet = 1 where ifnull(ups_per_sheet, 0) = 0")
	frappe.db.sql("update `tabBox Specification` set pricing_basis = 'Per Box' where ifnull(pricing_basis, '') = ''")
	frappe.db.sql(
		"""update `tabBox Specification` set artwork_status = 'Pending'
		where ifnull(artwork_status, '') = '' and ifnull(printing_type, 'None') != 'None'"""
	)
	frappe.db.sql(
		"""update `tabProduction Entry` set box_equivalent = output_qty, net_run_hrs = duration_hrs
		where ifnull(box_equivalent, 0) = 0"""
	)
	frappe.db.sql(
		"update `tabBox Costing` set approval_status = 'Not Required' where ifnull(approval_status, '') = ''"
	)
	frappe.db.sql("update `tabBox Costing` set pricing_basis = 'Per Box' where ifnull(pricing_basis, '') = ''")
