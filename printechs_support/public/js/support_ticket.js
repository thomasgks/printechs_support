// Copyright (c) 2026, Printechs and contributors
// License: MIT. See license.txt

/** Desk shortcuts for structured workflow (status transitions use server logic in ticket_workflow). */

function _wf_call(method, args) {
	return frappe.call({
		method,
		args,
		freeze: true,
		freeze_message: __("Updating…"),
	});
}

function _prompt_msg(title, callback) {
	frappe.prompt(
		{
			fieldname: "message",
			label: __("Message"),
			fieldtype: "Small Text",
			reqd: 1,
		},
		(values) => callback((values.message || "").trim()),
		title,
		__("Submit"),
	);
}

const GOOGLE_MEET_API = "printechs_support.printechs_support_system.api.google_meet";

function _open_meet(url) {
	if (!url) return;
	window.open(url, "_blank", "noopener,noreferrer");
}

function _escape_html(value) {
	const div = document.createElement("div");
	div.textContent = value || "";
	return div.innerHTML;
}

function _show_meet_result(r) {
	const data = r && r.message ? r.message : {};
	if (data.warning) {
		frappe.show_alert({ message: data.warning, indicator: "orange" }, 8);
	}
	if (data.meeting_url) {
		frappe.msgprint({
			title: __("Google Meet"),
			message: `<p>${__("Google Meet link:")} <a href="${_escape_html(data.meeting_url)}" target="_blank" rel="noopener noreferrer">${_escape_html(data.meeting_url)}</a></p>`,
			indicator: data.warning ? "orange" : "green",
		});
	}
}

frappe.ui.form.on("Support Ticket", {
	refresh(frm) {
		if (frm.is_new()) {
			return;
		}

		const base = "printechs_support.printechs_support_system.api.ticket_workflow";
		const meetUrl = (frm.doc.google_meet_url || "").trim();

		frm.add_custom_button(__("Help"), () => {
			if (window.printechs_help) {
				window.printechs_help.show_help({
					module_area: frm.doc.module_area || frm.doc.division || "Support",
					doctype: frm.doctype,
					docname: frm.doc.name,
					screen: frm.doc.ticket_type || frm.doc.subject || "Support Ticket",
					issue_type: frm.doc.related_issue_type || frm.doc.ticket_type || "",
					search: frm.doc.subject || "",
				});
			}
		});

		if (meetUrl) {
			frm.add_custom_button(__("Join Google Meet"), () => _open_meet(meetUrl), __("Google Meet"));
			frm.add_custom_button(
				__("Resend Meet Link"),
				() => {
					frappe.call({
						method: `${GOOGLE_MEET_API}.resend_google_meet_link`,
						args: { ticket_id: frm.doc.name },
						freeze: true,
						freeze_message: __("Sending Google Meet link…"),
					}).then((r) => {
						_show_meet_result(r);
						frm.reload_doc();
					});
				},
				__("Google Meet"),
			);
		} else {
			frm.add_custom_button(
				__("Enable Google Meet"),
				() => {
					frappe.call({
						method: `${GOOGLE_MEET_API}.create_google_meet`,
						args: {
							ticket_id: frm.doc.name,
							notify_customer: 1,
						},
						freeze: true,
						freeze_message: __("Creating Google Meet link…"),
					}).then((r) => {
						_show_meet_result(r);
						frm.reload_doc();
					});
				},
				__("Google Meet"),
			);
		}

		frm.add_custom_button(__("Workflow: Acknowledge"), () => {
			_prompt_msg(__("Acknowledgement"), (msg) => {
				if (!msg) return;
				_wf_call(`${base}.wf_technician_ack`, {
					ticket_name: frm.doc.name,
					message: msg,
				}).then(() => frm.reload_doc());
			});
		});

		frm.add_custom_button(__("Workflow: Start work"), () => {
			_prompt_msg(__("Start work"), (msg) => {
				_wf_call(`${base}.wf_start_work`, {
					ticket_name: frm.doc.name,
					message: msg || __("Started."),
				}).then(() => frm.reload_doc());
			});
		});

		frm.add_custom_button(__("Workflow: Request customer info"), () => {
			_prompt_msg(__("Request customer input"), (msg) => {
				if (!msg) return;
				_wf_call(`${base}.wf_request_customer_input`, {
					ticket_name: frm.doc.name,
					message: msg,
				}).then(() => frm.reload_doc());
			});
		});

		frm.add_custom_button(__("Workflow: Resolution"), () => {
			_prompt_msg(__("Send resolution"), (msg) => {
				if (!msg) return;
				_wf_call(`${base}.wf_send_resolution`, {
					ticket_name: frm.doc.name,
					message: msg,
				}).then(() => frm.reload_doc());
			});
		});

		frm.add_custom_button(__("Workflow: Cancel"), () => {
			frappe.prompt(
				{
					fieldname: "reason",
					label: __("Reason"),
					fieldtype: "Small Text",
				},
				(values) =>
					_wf_call(`${base}.wf_cancel`, {
						ticket_name: frm.doc.name,
						reason: (values.reason || "").trim(),
					}).then(() => frm.reload_doc()),
				__("Cancel ticket"),
				__("Confirm"),
			);
		});
	},
});
