import { useCallback, useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import type { PortalBootstrapResult } from "./api";
import { getPortalBootstrap, loginUrl } from "./api";
import AppShell from "./components/AppShell";
import CalendarPage from "./pages/CalendarPage";
import DashboardPage from "./pages/DashboardPage";
import LoginPage from "./pages/LoginPage";
import PlaceholderPage from "./pages/PlaceholderPage";
import CreateTaskPage from "./pages/CreateTaskPage";
import TaskDetailPage from "./pages/TaskDetailPage";
import TasksPage from "./pages/TasksPage";
import CreateTicketPage from "./pages/CreateTicketPage";
import TicketDetailPage from "./pages/TicketDetailPage";
import TicketsPage from "./pages/TicketsPage";

export default function App() {
	const [bootstrap, setBootstrap] = useState<PortalBootstrapResult | null>(null);
	const [error, setError] = useState<string | null>(null);
	const [loading, setLoading] = useState(true);

	const loadBootstrap = useCallback(async () => {
		setLoading(true);
		setError(null);
		try {
			const b = await getPortalBootstrap();
			setBootstrap(b);
		} catch (e) {
			setError(e instanceof Error ? e.message : "Could not load portal");
			setBootstrap(null);
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		loadBootstrap();
	}, [loadBootstrap]);

	if (loading) {
		return (
			<div className="center-stage">
				<div className="pulse-card">Loading portal…</div>
			</div>
		);
	}

	if (error) {
		return (
			<div className="center-stage">
				<div className="card login-card">
					<h2 className="card-title">Could not load portal</h2>
					<p className="muted">{error}</p>
					<p className="muted small">
						<a href={loginUrl()}>Open website login</a>
					</p>
				</div>
			</div>
		);
	}

	if (!bootstrap || !bootstrap.logged_in) {
		return <LoginPage onLoggedIn={loadBootstrap} />;
	}

	return (
		<AppShell bootstrap={bootstrap}>
			<Routes>
				<Route path="/" element={<DashboardPage />} />
				<Route path="/tickets/new" element={<CreateTicketPage />} />
				<Route path="/tickets/:ticketId" element={<TicketDetailPage />} />
				<Route path="/tickets" element={<TicketsPage />} />
				<Route path="/tasks/new" element={<CreateTaskPage />} />
				<Route path="/tasks/:taskId" element={<TaskDetailPage />} />
				<Route path="/tasks" element={<TasksPage />} />
				<Route path="/calendar" element={<CalendarPage />} />
				<Route
					path="/projects"
					element={
						<PlaceholderPage
							title="Projects"
							subtitle="Implementation projects, milestones, and Gantt — aligned with ERPNext Project links."
						/>
					}
				/>
				<Route
					path="/reports"
					element={
						<PlaceholderPage
							title="Reports"
							subtitle="Delay analytics, SLA, and engineer performance will aggregate from existing DocTypes."
						/>
					}
				/>
				<Route
					path="/customers"
					element={
						<PlaceholderPage
							title="Customers"
							subtitle="Customer-scoped views use your portal permissions (same as ticket visibility)."
						/>
					}
				/>
				<Route
					path="/settings"
					element={
						<PlaceholderPage
							title="Settings"
							subtitle="Portal preferences and notification channels — Desk remains source of truth for SLA rules."
						/>
					}
				/>
				<Route path="*" element={<Navigate to="/" replace />} />
			</Routes>
		</AppShell>
	);
}
