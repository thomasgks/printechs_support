// Copyright (c) 2026, Printechs and contributors
// Promote ERPNext Project Tasks (plan) → Support Ticket + Support Task

frappe.provide("printechs_support.project_promotion");

frappe.ui.form.on("Project", {
	refresh(frm) {
		if (frm.is_new()) {
			return;
		}
		frm.add_custom_button(
			__("Promote plan to Support"),
			() => printechs_support.project_promotion.open_dialog(frm),
			__("Printechs Support"),
		);
	},
});

printechs_support.project_promotion.open_dialog = function (frm) {
	frappe.call({
		method: "printechs_support.printechs_support_system.api.project_promotion.get_tasks_for_project_promotion",
		args: { project: frm.doc.name },
		freeze: true,
		callback(r) {
			const tasks = r.message || [];
			printechs_support.project_promotion._render_dialog(frm, tasks);
		},
	});
};

printechs_support.project_promotion._render_dialog = function (frm, tasks) {
	const esc = (s) => frappe.utils.escape_html(String(s ?? ""));

	let rows = "";
	for (const t of tasks) {
		const disabled = t.already_promoted ? "disabled" : "";
		const checked = t.already_promoted ? "" : "checked";
		const tag = t.already_promoted
			? `<span class="indicator-pill yellow">${__("Already promoted")}</span>`
			: "";
		rows += `<tr>
			<td style="width:36px"><input type="checkbox" class="promote-task-cb" data-name="${esc(
				t.name,
			)}" ${disabled} ${checked} /></td>
			<td><strong>${esc(t.subject || t.name)}</strong><div class="text-muted text-xs">${esc(t.name)}</div></td>
			<td>${esc(t.status || "")} ${tag}</td>
		</tr>`;
	}

	if (!rows) {
		frappe.msgprint(
			__(
				"No leaf tasks found. Add Tasks to this project first (Project → Tasks / Gantt), then promote.",
			),
		);
		return;
	}

	const table = `<div class="project-promote-scroll" style="max-height:min(360px,50vh);overflow:auto;border:1px solid var(--border-color);border-radius:var(--border-radius)">
		<table class="table table-bordered" style="margin:0">
			<thead><tr>
				<th style="width:36px"><input type="checkbox" class="promote-select-all" checked title="${__(
					"Select all",
				)}" /></th>
				<th>${__("Task")}</th>
				<th>${__("Status")}</th>
			</tr></thead>
			<tbody>${rows}</tbody>
		</table>
	</div>`;

	const d = new frappe.ui.Dialog({
		title: __("Promote project plan to Support"),
		fields: [
			{
				fieldname: "help",
				fieldtype: "HTML",
				options: `<p class="text-muted" style="margin-bottom:10px">${__(
					"Creates a Support Ticket and Support Tasks from the selected ERPNext Project Tasks. Use Project Tasks for internal planning; promote after the customer confirms.",
				)}</p>`,
			},
			{
				fieldname: "ticket_subject",
				fieldtype: "Data",
				label: __("New support ticket subject"),
				default: frm.doc.project_name || frm.doc.name,
				reqd: 1,
			},
			{
				fieldname: "new_ticket_status",
				fieldtype: "Select",
				label: __("New ticket status"),
				options: "Draft\nOpen",
				default: "Draft",
			},
			{ fieldname: "tasks_html", fieldtype: "HTML", label: __("Project tasks"), options: table },
		],
		primary_action_label: __("Promote"),
		primary_action(values) {
			const selected = [];
			d.$wrapper.find(".promote-task-cb:checked").each(function () {
				selected.push($(this).data("name"));
			});
			if (!selected.length) {
				frappe.msgprint(__("Select at least one task that is not already promoted."));
				return;
			}
			frappe.call({
				method: "printechs_support.printechs_support_system.api.project_promotion.promote_project_tasks_to_support",
				args: {
					project: frm.doc.name,
					task_names: selected,
					ticket_subject: values.ticket_subject,
					new_ticket_status: values.new_ticket_status,
				},
				freeze: true,
				callback(res) {
					const msg = res.message || {};
					const n = (msg.created_tasks || []).length;
					const sk = (msg.skipped || []).length;
					let html = `<p><strong>${__("Support Ticket")}:</strong> ${frappe.utils.escape_html(
						msg.support_ticket || "",
					)}</p>`;
					html += `<p><strong>${__("Support Tasks created")}:</strong> ${n}</p>`;
					if (sk) {
						html += `<p class="text-muted">${__("Skipped")}: ${sk}</p>`;
					}
					frappe.msgprint(html);
					d.hide();
					if (msg.support_ticket) {
						frappe.set_route("Form", "Support Ticket", msg.support_ticket);
					}
				},
			});
		},
	});

	d.show();

	d.$wrapper.on("change", ".promote-select-all", function () {
		const on = $(this).is(":checked");
		d.$wrapper.find(".promote-task-cb:not(:disabled)").prop("checked", on);
	});
};
