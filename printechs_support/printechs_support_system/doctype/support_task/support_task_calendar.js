// Copyright (c) 2026, Printechs and contributors
// License: MIT. See license.txt

frappe.views.calendar["Support Task"] = {
	field_map: {
		start: "planned_start_date",
		end: "planned_end_date",
		id: "name",
		title: "subject",
		progress: function (item) {
			const map = {
				Open: 0,
				"In Progress": 40,
				"Waiting for Customer": 25,
				"Waiting for Printechs": 25,
				Delayed: 45,
				Completed: 100,
				Cancelled: 0,
			};
			return map[item.status] || 0;
		},
	},
	gantt: true,
	filters: [
		{
			fieldtype: "Link",
			fieldname: "support_ticket",
			options: "Support Ticket",
			label: __("Support Ticket"),
		},
		{
			fieldtype: "Link",
			fieldname: "project",
			options: "Project",
			label: __("Project"),
		},
	],
	get_events_method:
		"printechs_support.printechs_support_system.api.support_calendar.get_support_task_events",
};
