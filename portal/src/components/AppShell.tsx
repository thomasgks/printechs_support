import { type ReactNode, useState } from "react";
import { NavLink } from "react-router-dom";
import type { PortalBootstrapResult } from "../api";
import { isPortalMockDataEnabled, portalHomeUrl, portalLogout } from "../api";
import PortalHeaderSearch from "./PortalHeaderSearch";

type ShellProps = {
	bootstrap: Extract<PortalBootstrapResult, { logged_in: true }>;
	children: ReactNode;
};

function NavIcon({ name }: { name: string }) {
	const common = "h-5 w-5 shrink-0";
	switch (name) {
		case "dashboard":
			return (
				<svg className={common} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden>
					<path d="M4 13h6V4H4v9zm0 7h6v-5H4v5zm10 0h6v-9h-6v9zm0-16v5h6V4h-6z" strokeLinejoin="round" />
				</svg>
			);
		case "ticket":
			return (
				<svg className={common} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden>
					<path d="M4 7a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v3a2 2 0 1 0 0 4v3a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-3a2 2 0 1 0 0-4V7z" />
				</svg>
			);
		case "task":
			return (
				<svg className={common} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden>
					<path d="M9 11l3 3L22 4" strokeLinecap="round" strokeLinejoin="round" />
					<path d="M21 12v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" strokeLinecap="round" />
				</svg>
			);
		case "project":
			return (
				<svg className={common} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden>
					<path d="M3 21h18M5 21V7l7-4 7 4v14M9 21v-8h6v8" strokeLinecap="round" strokeLinejoin="round" />
				</svg>
			);
		case "calendar":
			return (
				<svg className={common} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden>
					<rect x="3" y="4" width="18" height="18" rx="2" />
					<path d="M3 10h18M8 2v4M16 2v4" strokeLinecap="round" />
				</svg>
			);
		case "report":
			return (
				<svg className={common} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden>
					<path d="M4 19V5M9 19V9M14 19v-6M19 19V3" strokeLinecap="round" />
				</svg>
			);
		case "users":
			return (
				<svg className={common} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden>
					<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" strokeLinecap="round" />
				</svg>
			);
		case "settings":
			return (
				<svg className={common} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden>
					<circle cx="12" cy="12" r="3" />
					<path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" strokeLinecap="round" />
				</svg>
			);
		case "help":
			return (
				<svg className={common} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden>
					<circle cx="12" cy="12" r="10" />
					<path d="M9.5 9a2.5 2.5 0 015 0c0 1.8-2.5 2.2-2.5 4M12 17h.01" strokeLinecap="round" strokeLinejoin="round" />
				</svg>
			);
		default:
			return null;
	}
}

const nav = [
	{ to: "/", end: true, label: "Dashboard", icon: "dashboard" },
	{ to: "/tickets", label: "Tickets", icon: "ticket" },
	{ to: "/tasks", label: "Tasks", icon: "task" },
	{ to: "/projects", label: "Projects", icon: "project", internalOnly: true },
	{ to: "/calendar", label: "Calendar", icon: "calendar" },
	{ to: "/reports", label: "Reports", icon: "report", internalOnly: true },
	{ to: "/customers", label: "Customers", icon: "users", internalOnly: true },
	{ href: "__HELP_URL__", label: "Help", icon: "help" },
	{ to: "/settings", label: "Settings", icon: "settings", internalOnly: true },
] as const;

export default function AppShell({ bootstrap, children }: ShellProps) {
	const [signingOut, setSigningOut] = useState(false);
	const visibleNav = nav.filter((item) => !("internalOnly" in item) || !item.internalOnly || bootstrap.internal);
	const initial = (bootstrap.full_name || bootstrap.user || "?")
		.split(/\s+/)
		.map((s) => s[0])
		.join("")
		.slice(0, 2)
		.toUpperCase();

	async function signOut() {
		if (signingOut) {
			return;
		}
		setSigningOut(true);
		try {
			await portalLogout();
		} finally {
			window.location.assign(portalHomeUrl());
		}
	}

	return (
		<div className="app-root">
			<aside
				className="app-sidebar border-r border-slate-200 bg-white shadow-[4px_0_24px_rgba(15,23,42,0.04)]"
				aria-label="Primary navigation"
			>
				<div className="app-sidebar-brand">
					{bootstrap.brand_logo ? (
						<img className="shell-brand-logo" src={bootstrap.brand_logo} alt={bootstrap.brand_name || "Printechs Support"} />
					) : (
						<span className="shell-brand-mark" aria-hidden />
					)}
					<div className="min-w-0">
						<h1 className="shell-title truncate">{bootstrap.brand_name || "Support"}</h1>
						<p className="shell-sub truncate">{bootstrap.full_name}</p>
					</div>
				</div>
				<nav className="app-sidebar-nav">
					{visibleNav.map((item) => (
						"href" in item ? (
							<a
								key={item.href}
								href={item.href === "__HELP_URL__" ? bootstrap.help_url || "/help-center" : item.href}
								target="_blank"
								rel="noopener noreferrer"
								className="sidebar-link flex items-center gap-2"
							>
								<NavIcon name={item.icon} />
								<span>{item.label}</span>
							</a>
						) : (
							<NavLink
								key={item.to}
								to={item.to}
								end={"end" in item ? item.end : false}
								className={({ isActive }) =>
									`sidebar-link flex items-center gap-2 ${isActive ? "active" : ""}`
								}
							>
								<NavIcon name={item.icon} />
								<span>{item.label}</span>
							</NavLink>
						)
					))}
				</nav>
			</aside>
			<div className="app-main-wrap">
				{isPortalMockDataEnabled() ? (
					<p className="portal-mock-banner" role="status">
						Mock data — UI demo only. For production builds, unset{" "}
						<code className="portal-mock-code">VITE_PORTAL_USE_MOCK_DATA</code> or use{" "}
						<code className="portal-mock-code">?mock=0</code> to clear this tab.
					</p>
				) : null}
				<header className="sticky top-0 z-10 flex flex-wrap items-center gap-3 border-b border-slate-200/90 bg-white/95 px-4 py-3 backdrop-blur supports-[backdrop-filter]:bg-white/80 md:px-6">
					<PortalHeaderSearch />
					<div className="ml-auto flex items-center gap-2">
						<button
							type="button"
							className="relative rounded-xl border border-slate-200 bg-white p-2 text-slate-600 shadow-sm hover:border-violet-200 hover:text-violet-700"
							aria-label="Notifications"
							disabled
							title="Notifications — coming soon"
						>
							<svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
								<path d="M18 8a6 6 0 10-12 0c0 7-3 7-3 7h18s-3 0-3-7M13.73 21a2 2 0 01-3.46 0" strokeLinecap="round" />
							</svg>
							<span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-violet-500 ring-2 ring-white" />
						</button>
						<details className="shell-user-menu relative">
							<summary
								className="flex cursor-pointer list-none items-center gap-2 rounded-xl border border-slate-200 bg-white py-1 pl-1 pr-2 shadow-sm transition hover:border-violet-200 [&::-webkit-details-marker]:hidden"
								aria-label="Profile menu"
							>
								<div
									className="flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500 to-blue-700 text-xs font-bold text-white shadow-inner ring-2 ring-white"
									title={bootstrap.user}
								>
									{initial}
								</div>
								<span className="hidden max-w-[8rem] truncate text-xs font-semibold text-slate-700 sm:inline">
									{bootstrap.full_name || bootstrap.user}
								</span>
								<svg className="h-4 w-4 shrink-0 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
									<path d="M6 9l6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
								</svg>
							</summary>
							<div className="absolute right-0 z-30 mt-1 min-w-[min(100vw-2rem,14rem)] overflow-hidden rounded-xl border border-slate-200 bg-white py-1 shadow-lg ring-1 ring-slate-200/80">
								<div className="border-b border-slate-100 px-3 py-2">
									<p className="truncate text-xs font-semibold text-slate-900">{bootstrap.full_name || bootstrap.user}</p>
									<p className="truncate text-[11px] text-slate-500">{bootstrap.user}</p>
								</div>
								<button
									type="button"
									onClick={signOut}
									disabled={signingOut}
									className="block w-full border-0 bg-transparent px-3 py-2.5 text-left text-sm font-semibold text-slate-800 hover:bg-slate-50 disabled:cursor-wait disabled:text-slate-500"
								>
									{signingOut ? "Signing out..." : "Sign out"}
								</button>
							</div>
						</details>
					</div>
				</header>
				<main className="app-main">{children}</main>
				<footer className="shell-footer">
					<span className="muted">
						{bootstrap.internal ? "Internal view · " : ""}
						{bootstrap.customers.length
							? `${bootstrap.customers.length} linked customer(s)`
							: bootstrap.internal
								? "All records (role)"
								: "No customer link yet"}
					</span>
				</footer>
			</div>
		</div>
	);
}
