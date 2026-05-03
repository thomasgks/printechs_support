// Copyright (c) 2026, Printechs and contributors
// License: MIT. See license.txt

// List shows title as the main column; hide technical document name ("ID") and bulk row checkboxes.
frappe.listview_settings["Coverage Type"] = {
	hide_name_column: true,
	refresh(listview) {
		listview.$result.find(".list-check-all, .list-row-checkbox").hide();
	},
};
