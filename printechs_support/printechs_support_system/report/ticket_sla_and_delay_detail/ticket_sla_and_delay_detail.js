frappe.query_reports["Ticket SLA and Delay Detail"] = {
	filters: [
		{
			fieldname: "from_date",
			fieldtype: "Date",
			label: __("From Date"),
			mandatory: 1,
			default: frappe.datetime.month_start(),
		},
		{
			fieldname: "to_date",
			fieldtype: "Date",
			label: __("To Date"),
			mandatory: 1,
			default: frappe.datetime.month_end(),
		},
		{
			fieldname: "period_based_on",
			fieldtype: "Select",
			label: __("Period based on"),
			options: ["Resolved Date", "Opening Date", "Closed Date"],
			default: "Resolved Date",
		},
		{
			fieldname: "customer",
			fieldtype: "Link",
			label: __("Customer"),
			options: "Customer",
		},
		{
			fieldname: "status",
			fieldtype: "Select",
			label: __("Status"),
			options: [
				"",
				"Open",
				"Assigned",
				"In Progress",
				"Hold",
				"Waiting for Customer",
				"Waiting for Technician",
				"Reopened",
				"Resolved",
				"Closed",
				"Cancelled",
			],
		},
		{
			fieldname: "work_scope",
			fieldtype: "Select",
			label: __("Work scope"),
			options: ["", "Customer", "Internal"],
		},
	],
	onload(report) {
		if (report.__ps_sla_print_patched) {
			return;
		}
		report.__ps_sla_print_patched = true;

		const print_report = report.print_report.bind(report);
		report.print_report = (print_settings) => {
			if (print_settings) {
				delete print_settings.columns;
			}
			return print_report(print_settings);
		};

		const pdf_report = report.pdf_report.bind(report);
		report.pdf_report = (print_settings) => {
			if (print_settings) {
				delete print_settings.columns;
			}
			return pdf_report(print_settings);
		};
	},
};
