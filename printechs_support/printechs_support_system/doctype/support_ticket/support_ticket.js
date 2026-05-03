// Copyright (c) 2026, Printechs and contributors
// License: MIT. See license.txt

frappe.ui.form.on("Support Ticket", {
	setup(frm) {
		frm.set_query("coverage_type", () => ({
			filters: { division: frm.doc.division || "" },
		}));
	},
	work_scope(frm) {
		if (frm.doc.work_scope === "Internal") {
			frm.set_value("customer", null);
			frm.set_value("support_agreement", null);
			if (!frm.doc.channel || frm.doc.channel === "Portal") {
				frm.set_value("channel", "Internal");
			}
		}
	},
	division(frm) {
		frm.set_value("coverage_type", null);
	},
	coverage_type(frm) {
		if (frm.doc.coverage_type) {
			frappe.db.get_value("Coverage Type", frm.doc.coverage_type, "title").then((r) => {
				if (r && r.message && r.message.title) {
					frm.set_value("service_category", r.message.title);
				}
			});
		}
	},
});
