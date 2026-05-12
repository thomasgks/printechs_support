frappe.query_reports["Ticket SLA and Delay Detail"] = {
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
