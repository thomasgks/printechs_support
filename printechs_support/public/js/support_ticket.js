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

frappe.ui.form.on("Support Ticket", {
	refresh(frm) {
		if (frm.is_new()) {
			return;
		}

		const base = "printechs_support.printechs_support_system.api.ticket_workflow";

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
