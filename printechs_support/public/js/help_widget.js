(function () {
	function esc(value) {
		const div = document.createElement("div");
		div.textContent = value || "";
		return div.innerHTML;
	}

	function articleListHtml(articles) {
		if (!articles || !articles.length) {
			return `<p class="text-muted">${__("No help articles found.")}</p>`;
		}
		return articles
			.map(
				(a) => `
				<div class="printechs-help-row" data-name="${esc(a.name)}" style="padding:10px 0;border-bottom:1px solid var(--border-color,#e5e7eb);cursor:pointer;">
					<div style="font-weight:600;color:#111827;">${esc(a.title)}</div>
					<div style="font-size:12px;color:#6b7280;margin-top:3px;">${esc(a.summary || "")}</div>
					<div style="font-size:11px;color:#64748b;margin-top:5px;">
						${esc(a.module_area || "General")} · ${esc(a.category || "")}
						${a.has_video ? " · Video" : ""}
						${a.attachments_count ? ` · ${a.attachments_count} attachment(s)` : ""}
					</div>
				</div>`,
			)
			.join("");
	}

	function detailHtml(article) {
		const attachments = (article.attachments || [])
			.map((att) => {
				const href = att.file || att.external_url || "";
				const label = att.attachment_title || href || __("Attachment");
				return href
					? `<li><a href="${esc(href)}" target="_blank" rel="noopener noreferrer">${esc(label)}</a>${att.description ? `<br><small>${esc(att.description)}</small>` : ""}</li>`
					: `<li>${esc(label)}</li>`;
			})
			.join("");
		return `
			<div>
				<button class="btn btn-xs btn-default printechs-help-back" type="button">${__("Back")}</button>
				<h3 style="margin-top:12px;">${esc(article.title)}</h3>
				${article.summary ? `<p class="text-muted">${esc(article.summary)}</p>` : ""}
				${article.video_embed_html || ""}
				<div style="margin-top:12px;">${article.content || ""}</div>
				${attachments ? `<hr><h5>${__("Attachments")}</h5><ul>${attachments}</ul>` : ""}
			</div>`;
	}

	async function loadArticles(opts) {
		const r = await frappe.call({
			method: "printechs_support.api.help_article.get_contextual_help",
			args: {
				module_area: opts.module_area || "",
				doctype: opts.doctype || "",
				screen: opts.screen || "",
				issue_type: opts.issue_type || "",
				search: opts.search || "",
				limit: opts.limit || 12,
			},
		});
		return (r.message && r.message.articles) || [];
	}

	async function loadDetail(name) {
		const r = await frappe.call({
			method: "printechs_support.api.help_article.get_help_article_detail",
			args: { name },
		});
		return r.message && r.message.article;
	}

	window.printechs_help = {
		async show_help(opts) {
			opts = opts || {};
			const dialog = new frappe.ui.Dialog({
				title: opts.title || __("Help"),
				size: "large",
				fields: [{ fieldtype: "HTML", fieldname: "body" }],
			});
			const body = dialog.fields_dict.body.$wrapper;
			body.html(`<p class="text-muted">${__("Loading help articles...")}</p>`);
			dialog.show();

			let articles = [];
			try {
				articles = await loadArticles(opts);
				body.html(articleListHtml(articles));
			} catch (e) {
				body.html(`<p class="text-danger">${esc(e.message || __("Could not load help articles."))}</p>`);
			}

			body.on("click", ".printechs-help-row", async function () {
				const name = this.getAttribute("data-name");
				body.html(`<p class="text-muted">${__("Loading article...")}</p>`);
				try {
					const article = await loadDetail(name);
					body.html(detailHtml(article));
				} catch (e) {
					body.html(`<p class="text-danger">${esc(e.message || __("Could not load article."))}</p>`);
				}
			});

			body.on("click", ".printechs-help-back", function () {
				body.html(articleListHtml(articles));
			});
		},
	};
})();
