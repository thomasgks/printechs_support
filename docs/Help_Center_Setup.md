# Help Center Setup

The Help Center is a generic knowledge base for Support, WMS, ERPNext, Sales, Purchase, Stock, Accounts, HR, and future modules.

## Public Routes

- `/help-center`
- `/help-center/<category>`
- `/help-article/<article-name>`

Guest users can only see articles where:

- `is_published = 1`
- `show_in_portal = 1`
- `allow_customer_view = 1`

## API Methods

- `printechs_support.api.help_article.get_help_articles`
- `printechs_support.api.help_article.get_help_article_detail`
- `printechs_support.api.help_article.get_contextual_help`
- `printechs_support.api.help_article.create_help_article`

Example WMS/mobile call:

```text
/api/method/printechs_support.api.help_article.get_contextual_help?module_area=WMS&doctype=WMS%20ASN&screen=Receiving&search=barcode
```

## Desk Widget

`public/js/help_widget.js` exposes:

```javascript
printechs_help.show_help({
  module_area: "WMS",
  doctype: frm.doctype,
  docname: frm.doc.name,
  screen: "ASN Receiving"
});
```

Example client script:

```javascript
frappe.ui.form.on("WMS ASN", {
  refresh(frm) {
    frm.add_custom_button("Help", function() {
      printechs_help.show_help({
        module_area: "WMS",
        doctype: frm.doctype,
        docname: frm.doc.name,
        screen: "ASN Receiving"
      });
    });
  }
});
```

## Migration

```bash
bench --site demo migrate
bench --site demo clear-cache
bench restart
```
