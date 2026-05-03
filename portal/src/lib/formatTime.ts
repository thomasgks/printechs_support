export function formatCommentTime(iso: string | null | undefined): string {
	if (!iso) return "";
	try {
		const d = new Date(iso.replace(" ", "T"));
		if (Number.isNaN(d.getTime())) return String(iso);
		return new Intl.DateTimeFormat(undefined, {
			month: "short",
			day: "numeric",
			hour: "2-digit",
			minute: "2-digit",
		}).format(d);
	} catch {
		return String(iso);
	}
}

export function formatFileSize(n: number | undefined): string {
	if (n == null || Number.isNaN(n)) return "";
	if (n < 1024) return `${n} B`;
	if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
	return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}
