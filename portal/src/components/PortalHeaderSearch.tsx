import { FormEvent, useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

/**
 * Top bar search: jumps to /tickets with ?q=… so the Tickets page can apply the same ID search.
 */
export default function PortalHeaderSearch() {
	const navigate = useNavigate();
	const location = useLocation();
	const [value, setValue] = useState("");

	useEffect(() => {
		const onTickets = location.pathname === "/tickets" || location.pathname.endsWith("/tickets");
		if (!onTickets) {
			return;
		}
		const q = new URLSearchParams(location.search).get("q") ?? "";
		setValue(q);
	}, [location.pathname, location.search]);

	const onSubmit = (e: FormEvent) => {
		e.preventDefault();
		const q = value.trim();
		navigate({
			pathname: "/tickets",
			search: q ? `?q=${encodeURIComponent(q)}` : "",
		});
	};

	return (
		<form className="relative min-w-[12rem] max-w-xl flex-1" onSubmit={onSubmit}>
			<span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" aria-hidden>
				<svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
					<circle cx="11" cy="11" r="7" />
					<path d="M21 21l-4.3-4.3" strokeLinecap="round" />
				</svg>
			</span>
			<input
				type="search"
				className="w-full rounded-xl border border-slate-200 bg-slate-50 py-2 pl-9 pr-3 text-sm text-slate-800 outline-none ring-violet-500/20 placeholder:text-slate-400 focus:border-violet-400 focus:bg-white focus:ring-4"
				placeholder="Search tickets by ID… (Enter)"
				value={value}
				onChange={(e) => setValue(e.target.value)}
				aria-label="Search tickets by ID"
			/>
		</form>
	);
}
