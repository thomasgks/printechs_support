// Copyright (c) 2026, Printechs and contributors
// License: MIT. See license.txt

frappe.ui.form.on("Support Agreement", {
	setup(frm) {
		frm.set_query("coverage_type", "coverage_detail", () => ({
			filters: { division: frm.doc.division || "" },
		}));
	},
	division(frm) {
		frm.refresh_field("coverage_detail");
	},
});

frappe.ui.form.on("Support Agreement Coverage Detail", {
	coverage_type(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row.coverage_type) {
			frappe.db.get_value("Coverage Type", row.coverage_type, "title").then((r) => {
				if (r && r.message && r.message.title) {
					frappe.model.set_value(cdt, cdn, "service_category", r.message.title);
				}
			});
		}
	},
});
