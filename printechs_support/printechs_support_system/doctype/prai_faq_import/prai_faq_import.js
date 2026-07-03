// Copyright (c) 2026, Printechs and contributors
// License: MIT. See license.txt

frappe.ui.form.on("PRAI FAQ Import", {
	refresh(frm) {
		if (frm.is_new()) {
			return;
		}
		frm.add_custom_button(__("1. Extract Text"), () => run_import_step(frm, "extract_document"), __("PRAI Import"));
		frm.add_custom_button(__("2. Generate FAQ Preview"), () => run_import_step(frm, "generate_preview"), __("PRAI Import"));
		const importBtn = frm.add_custom_button(
			__("3. Save to PRAI FAQ (required for chat)"),
			() => run_import_step(frm, "import_selected_faqs"),
			__("PRAI Import")
		);
		if (importBtn) {
			importBtn.addClass("btn-primary");
		}

		if (frm.doc.status === "Preview Ready") {
			frm.dashboard.set_headline_alert(
				__(
					"Preview only — PRAI Assistant cannot use these FAQs until you click <b>3. Save to PRAI FAQ</b>."
				),
				"orange"
			);
		} else if (frm.doc.status === "Imported") {
			frm.dashboard.set_headline_alert(
				__("Saved to PRAI FAQ. Users can now get these answers in PRAI Assistant."),
				"green"
			);
		}
	},
});

function run_import_step(frm, method) {
	frm.call(method).then((r) => {
		const msg = r.message || {};
		if (msg.generated) {
			frappe.msgprint({
				title: __("Preview generated — one more step"),
				indicator: "orange",
				message: __(
					"Generated {0} FAQ proposal(s). Review the table, then click <b>3. Save to PRAI FAQ (required for chat)</b>. PRAI Assistant will not use these until that step is done.",
					[msg.generated]
				),
			});
		} else if (msg.created !== undefined) {
			frappe.msgprint({
				title: __("Saved to PRAI FAQ"),
				indicator: "green",
				message: __(
					"Import complete — created: {0}, updated: {1}, skipped: {2}. PRAI Assistant can now answer from these FAQs.",
					[msg.created, msg.updated, msg.skipped]
				),
			});
		} else if (msg.characters) {
			frappe.msgprint(__("Extracted {0} characters from the document.", [msg.characters]));
		}
		frm.reload_doc();
	});
}
