frappe.ui.form.on("PRAI Source Scan Run", {
	refresh(frm) {
		if (frm.is_new() || frm.doc.status !== "Extracted") {
			return;
		}

		frm.add_custom_button(__("Create Knowledge Run"), () => {
			frm.call("create_knowledge_run").then((r) => {
				if (r.message?.name) {
					frappe.show_alert({
						message: r.message.existing
							? __("Opened existing knowledge run")
							: __("Knowledge run created"),
						indicator: "green",
					});
					frappe.set_route("Form", "PRAI Studio Knowledge Run", r.message.name);
				}
			});
		}).addClass("btn-primary");

		if (frm.doc.latest_knowledge_run) {
			frm.add_custom_button(__("Open Knowledge Run"), () => {
				frappe.set_route("Form", "PRAI Studio Knowledge Run", frm.doc.latest_knowledge_run);
			});
		}
	},
});
