frappe.ui.form.on("PRAI Studio Knowledge Run", {
	refresh(frm) {
		if (frm.is_new()) {
			return;
		}

		if (["Draft", "Failed", "Analyzed"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Run Health Checks"), () => {
				frm.call("run_health_checks_action").then((r) => {
					if (r.message?.success) {
						frappe.show_alert({
							message: __("Health checks: {0} warning(s)", [r.message.warnings || 0]),
							indicator: r.message.warnings ? "orange" : "green",
						});
						frm.reload_doc();
					}
				});
			});
		}

		if (["Draft", "Failed"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Run Source Analysis"), () => {
				frm.call("run_analysis").then((r) => {
					if (r.message?.success) {
						frappe.show_alert({
							message: __("Analysis completed: {0} finding(s)", [r.message.findings || 0]),
							indicator: "green",
						});
						frm.reload_doc();
					}
				});
			}).addClass("btn-primary");
		}

		if (["Analyzed", "Generated", "In Review"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Generate Draft Content"), () => {
				frm.call("generate_faqs").then((r) => {
					if (r.message?.success) {
						frappe.show_alert({
							message: __("Generated {0} FAQ(s), {1} Help Article(s)", [
								r.message.generated || 0,
								r.message.help_generated || 0,
							]),
							indicator: "green",
						});
						frm.reload_doc();
					}
				});
			}).addClass("btn-primary");

			frm.add_custom_button(__("Generate Help Articles Only"), () => {
				frm.call("generate_help_articles").then((r) => {
					if (r.message?.success) {
						frappe.show_alert({
							message: __("Generated {0} Help Article(s)", [r.message.help_generated || 0]),
							indicator: "green",
						});
						frm.reload_doc();
					}
				});
			});
		}

		if (["Generated", "In Review"].includes(frm.doc.status)) {
			const hasDrafts = (frm.doc.draft_items || []).length || (frm.doc.draft_help_items || []).length;
			if (hasDrafts) {
				frm.add_custom_button(__("Submit for Review"), () => {
					frm.call("submit_for_review").then((r) => {
						if (r.message?.success) {
							frappe.show_alert({ message: __("Submitted for review"), indicator: "blue" });
							frm.reload_doc();
						}
					});
				});
			}
		}

		if (frm.doc.status === "In Review") {
			frm.add_custom_button(__("Approve Selected"), () => {
				frm.call("approve_selected").then((r) => {
					if (r.message?.success) {
						frappe.show_alert({
							message: __("Approved {0} item(s)", [r.message.approved || 0]),
							indicator: "green",
						});
						frm.reload_doc();
					}
				});
			}).addClass("btn-success");

			frm.add_custom_button(__("Reject Selected"), () => {
				frm.call("reject_selected").then((r) => {
					if (r.message?.success) {
						frappe.show_alert({
							message: __("Rejected {0} item(s)", [r.message.rejected || 0]),
							indicator: "orange",
						});
						frm.reload_doc();
					}
				});
			});

			frm.add_custom_button(__("Publish Approved to PRAI"), () => {
				frappe.confirm(
					__(
						"Publish approved FAQs and Help Articles to live PRAI Agent? They will become searchable in chat and Help Center."
					),
					() => {
						frm.call("publish_approved").then((r) => {
							if (r.message?.success) {
								frappe.show_alert({
									message: __("Published to PRAI Agent"),
									indicator: "green",
								});
								frm.reload_doc();
							}
						});
					}
				);
			}).addClass("btn-primary");
		}

		if (frm.doc.latest_publish_log) {
			frm.add_custom_button(__("Open Publish Log"), () => {
				frappe.set_route("Form", "PRAI Publish Log", frm.doc.latest_publish_log);
			});
		}
	},
});
