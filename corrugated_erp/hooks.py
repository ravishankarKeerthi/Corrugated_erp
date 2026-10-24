app_name = "corrugated_erp"
app_title = "Corrugated ERP"
app_publisher = "Syvasoft Business Solutions"
app_description = "Corrugated box & packaging ERP on ERPNext - box costing, reel tracking, deckle planning, stage-wise production, quality and dispatch"
app_email = "ravimba2005@rediffmail.com"
app_license = "mit"
required_apps = ["erpnext"]
app_logo_url = "/assets/corrugated_erp/images/corrugated-erp-logo.svg"
app_home = "/app/corrugation"

# Own tile on the apps screen (/apps) and in the app switcher
add_to_apps_screen = [
	{
		"name": app_name,
		"logo": app_logo_url,
		"title": app_title,
		"route": app_home,
		"has_permission": "corrugated_erp.api.check_app_permission",
	}
]

# Install / migrate
after_install = "corrugated_erp.install.after_install"
after_migrate = "corrugated_erp.install.after_migrate"

# Client scripts on standard ERPNext forms
doctype_js = {
	"Item": "public/js/item.js",
	"Quotation": "public/js/box_selling.js",
	"Sales Order": "public/js/box_selling.js",
	"Work Order": "public/js/work_order.js",
	"Delivery Note": "public/js/delivery_note.js",
}

# Document events on standard ERPNext documents
doc_events = {
	"Item": {"validate": "corrugated_erp.events.stock.item_validate"},
	"Work Order": {"validate": "corrugated_erp.events.stock.work_order_validate"},
	"Delivery Note": {"validate": "corrugated_erp.events.stock.delivery_note_validate"},
	"Purchase Receipt": {
		"on_submit": "corrugated_erp.events.stock.purchase_receipt_on_submit",
		"on_cancel": "corrugated_erp.events.stock.purchase_receipt_on_cancel",
	},
	"Stock Entry": {
		"on_submit": "corrugated_erp.events.stock.stock_entry_on_submit_or_cancel",
		"on_cancel": "corrugated_erp.events.stock.stock_entry_on_submit_or_cancel",
	},
	"Stock Reconciliation": {
		"on_submit": "corrugated_erp.events.stock.stock_reco_on_submit_or_cancel",
		"on_cancel": "corrugated_erp.events.stock.stock_reco_on_submit_or_cancel",
	},
}

# Barcode / QR helpers for print formats
jinja = {
	"methods": [
		"corrugated_erp.utils.barcode.code128_svg",
		"corrugated_erp.utils.barcode.qr_svg",
	]
}

# Remove app custom fields cleanly on uninstall
before_uninstall = "corrugated_erp.uninstall.before_uninstall"
