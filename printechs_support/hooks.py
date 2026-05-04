app_name = "printechs_support"
app_title = "Printechs Support System"
app_publisher = "Printechs"
app_description = "Printechs Support"
app_email = "sakeer@printechs.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "printechs_support",
# 		"logo": "/assets/printechs_support/logo.png",
# 		"title": "Printechs Support System",
# 		"route": "/printechs_support",
# 		"has_permission": "printechs_support.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/printechs_support/css/printechs_support.css"
app_include_js = "/assets/printechs_support/js/help_widget.js"

# include js, css files in header of web template
# web_include_css = "/assets/printechs_support/css/printechs_support.css"
# web_include_js = "/assets/printechs_support/js/printechs_support.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "printechs_support/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
	"Project": "public/js/project_printechs_support.js",
	"Support Ticket": "public/js/support_ticket.js",
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "printechs_support/public/icons.svg"

# Home Pages
# ----------

# React SPA: deep links like /support-portal/tickets/TICKET-NAME must serve the same shell as /support-portal
# (same pattern as Frappe core: /app/<path:app_path> → app).
website_route_rules = [
	{"from_route": "/support-portal/<path:app_path>", "to_route": "support-portal"},
	{"from_route": "/help-center/<path:category>", "to_route": "help-center"},
	{"from_route": "/help-article/<path:article_name>", "to_route": "help-article"},
]

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "printechs_support.utils.jinja_methods",
# 	"filters": "printechs_support.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "printechs_support.install.before_install"
after_install = "printechs_support.install.after_install"

# Sync workspace + settings after migrate (desk menu completeness across sites)
after_migrate = ["printechs_support.install.after_migrate"]

# Uninstallation
# ------------

# before_uninstall = "printechs_support.uninstall.before_uninstall"
# after_uninstall = "printechs_support.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "printechs_support.utils.before_app_install"
# after_app_install = "printechs_support.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "printechs_support.utils.before_app_uninstall"
# after_app_uninstall = "printechs_support.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "printechs_support.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

permission_query_conditions = {
	"Support Ticket": "printechs_support.permissions.support_ticket_permission_query_conditions",
	"Support Task": "printechs_support.permissions.support_task_permission_query_conditions",
	"Help Article": "printechs_support.permissions.help_article_permission_query_conditions",
}

has_permission = {
	"Support Ticket": "printechs_support.permissions.support_ticket_has_permission",
	"Support Task": "printechs_support.permissions.support_task_has_permission",
	"Help Article": "printechs_support.permissions.help_article_has_permission",
}

# DocType Class
# ---------------
# Override standard doctype classes

override_doctype_class = {
	"Notification": "printechs_support.overrides.notification.PrintechsSupportNotification",
}

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"User": {
		"before_insert": "printechs_support.printechs_support_system.api.user_hooks.before_insert_user",
		"after_insert": "printechs_support.printechs_support_system.api.user_hooks.after_insert_user",
	}
}

# Scheduled Tasks
# ---------------

scheduler_events = {
	"daily": [
		"printechs_support.tasks.daily",
	],
	"hourly": [
		"printechs_support.tasks.hourly",
	],
}

# Testing
# -------

# before_tests = "printechs_support.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "printechs_support.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
override_doctype_dashboards = {
	"Project": "printechs_support.printechs_support_system.dashboard.project_dashboard.extend_project_dashboard",
}

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["printechs_support.utils.before_request"]
# after_request = ["printechs_support.utils.after_request"]

# Job Events
# ----------
# before_job = ["printechs_support.utils.before_job"]
# after_job = ["printechs_support.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"printechs_support.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

