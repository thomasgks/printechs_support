import { useQuery } from '@tanstack/react-query';
import { Link } from 'expo-router';
import { RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';

import { useAuth } from '@/context/AuthContext';
import { getPortalDashboardStats } from '@/lib/portal';
import { palette } from '@/constants/palette';

function StatCard({ label, value, tone }: { label: string; value: number; tone?: 'default' | 'warn' | 'ok' }) {
	const c =
		tone === 'warn' ? palette.danger : tone === 'ok' ? palette.success : palette.text;
	return (
		<View style={styles.card}>
			<Text style={styles.cardLabel}>{label}</Text>
			<Text style={[styles.cardValue, { color: c }]}>{value}</Text>
		</View>
	);
}

export default function HomeScreen() {
	const { bootstrap, refreshBootstrap } = useAuth();
	const internal = bootstrap?.logged_in && bootstrap.internal;

	const q = useQuery({
		queryKey: ['dashboard-stats'],
		queryFn: getPortalDashboardStats,
	});

	return (
		<ScrollView
			style={styles.root}
			contentContainerStyle={styles.content}
			refreshControl={
				<RefreshControl
					refreshing={q.isFetching}
					onRefresh={() => {
						void refreshBootstrap();
						void q.refetch();
					}}
					tintColor={palette.accent}
				/>
			}>
			<Text style={styles.hello}>
				Hello{bootstrap?.logged_in ? `, ${bootstrap.full_name}` : ''}
			</Text>
			<Text style={styles.role}>
				{internal ? 'Team / Management' : 'Customer'} ·{' '}
				{bootstrap?.logged_in && !internal ? `${bootstrap.customers?.length ?? 0} linked customer(s)` : 'Internal view'}
			</Text>

			{q.isError ? (
				<Text style={styles.err}>{q.error instanceof Error ? q.error.message : 'Could not load dashboard'}</Text>
			) : null}

			{q.data ? (
				<>
					<Text style={styles.section}>Today</Text>
					<View style={styles.row}>
						<StatCard label="Open tickets" value={q.data.pending_tickets} />
						<StatCard label="Overdue tickets" value={q.data.overdue_tickets} tone="warn" />
					</View>
					<View style={styles.row}>
						<StatCard label="Pending tasks" value={q.data.pending_tasks} />
						<StatCard label="Overdue tasks" value={q.data.overdue_tasks} tone="warn" />
					</View>
					<View style={styles.row}>
						<StatCard label="Done today" value={q.data.completed_today} tone="ok" />
						<StatCard label="SLA risk" value={q.data.sla_breached} tone="warn" />
					</View>

					{internal ? (
						<>
							<Text style={styles.section}>Queues</Text>
							<View style={styles.row}>
								<StatCard label="Waiting customer" value={q.data.tickets_waiting_customer} />
								<StatCard label="Waiting internal" value={q.data.tickets_waiting_internal} />
							</View>
						</>
					) : null}
				</>
			) : (
				<Text style={styles.muted}>Pull to refresh or open Tickets / Tasks.</Text>
			)}

			<Link href="/new-ticket" asChild>
				<Text style={styles.cta}>+ New ticket</Text>
			</Link>
		</ScrollView>
	);
}

const styles = StyleSheet.create({
	root: { flex: 1, backgroundColor: palette.bg },
	content: { padding: 20, paddingBottom: 40 },
	hello: { fontSize: 26, fontWeight: '800', color: palette.text, letterSpacing: -0.5 },
	role: { fontSize: 14, color: palette.textMuted, marginTop: 6, marginBottom: 24 },
	section: {
		fontSize: 12,
		fontWeight: '700',
		color: palette.textMuted,
		textTransform: 'uppercase',
		letterSpacing: 1,
		marginBottom: 12,
		marginTop: 8,
	},
	row: { flexDirection: 'row', gap: 12, marginBottom: 12 },
	card: {
		flex: 1,
		backgroundColor: palette.bgCard,
		borderRadius: 16,
		padding: 16,
		borderWidth: 1,
		borderColor: palette.border,
	},
	cardLabel: { fontSize: 12, color: palette.textMuted, marginBottom: 4 },
	cardValue: { fontSize: 28, fontWeight: '800' },
	err: { color: palette.danger, marginBottom: 12 },
	muted: { color: palette.textMuted, marginTop: 8 },
	cta: {
		marginTop: 28,
		fontSize: 17,
		fontWeight: '700',
		color: palette.accent,
		textAlign: 'center',
		padding: 16,
		backgroundColor: palette.bgElevated,
		borderRadius: 14,
		overflow: 'hidden',
	},
});
