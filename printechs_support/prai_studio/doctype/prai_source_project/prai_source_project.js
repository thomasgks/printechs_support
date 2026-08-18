frappe.ui.form.on("PRAI Source Project", {
	refresh(frm) {
		if (frm.is_new() || frm.doc.status === "Extracting") {
			return;
		}
		if (!frm.doc.source_zip) {
			return;
		}
		frm.add_custom_button(__("Extract and Scan Source"), () => {
			frappe.confirm(
				__(
					"Extract the ZIP securely and scan source files? This may take a minute for large projects."
				),
				() => {
					frm.call("extract_and_scan").then((r) => {
						if (r.message?.success) {
							frappe.show_alert({
								message: __("Scan completed: {0} scannable file(s)", [
									r.message.scanned_files || 0,
								]),
								indicator: "green",
							});
							frm.reload_doc();
						}
					});
				}
			);
		}).addClass("btn-primary");

		if (frm.doc.latest_scan_run) {
			frm.add_custom_button(__("Open Scan Results"), () => {
				frappe.set_route("Form", "PRAI Source Scan Run", frm.doc.latest_scan_run);
			});
		}
	},
});
