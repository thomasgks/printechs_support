import { useQuery } from '@tanstack/react-query';
import { Link } from 'expo-router';
import { useMemo } from 'react';
import { SectionList, Pressable, RefreshControl, StyleSheet, Text, View } from 'react-native';

import { getPortalTasks } from '@/lib/portal';
import { palette } from '@/constants/palette';

function dayKey(iso: string | null | undefined, calendar?: string | null | undefined): string {
	// Prefer API `due_date_calendar` — naive `YYYY-MM-DD HH:mm:ss` + Date/toISOString() shifts the UTC day.
	const c = (calendar ?? '').trim();
	if (/^\d{4}-\d{2}-\d{2}$/.test(c)) return c;
	if (!iso) return 'Unscheduled';
	const s = String(iso).trim();
	const prefix = /^(\d{4}-\d{2}-\d{2})/.exec(s);
	if (prefix) return prefix[1];
	const d = new Date(s);
	if (Number.isNaN(d.getTime())) return 'Unscheduled';
	return d.toISOString().slice(0, 10);
}

function labelDay(key: string): string {
	if (key === 'Unscheduled') return 'Unscheduled';
	const d = new Date(key + 'T12:00:00Z');
	const today = new Date();
	const t0 = new Date(today.getFullYear(), today.getMonth(), today.getDate());
	const d0 = new Date(d.getFullYear(), d.getMonth(), d.getDate());
	const diff = Math.round((d0.getTime() - t0.getTime()) / 86400000);
	if (diff === 0) return 'Today';
	if (diff === 1) return 'Tomorrow';
	if (diff === -1) return 'Yesterday';
	return d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
}

export default function AgendaScreen() {
	const q = useQuery({
		queryKey: ['portal-tasks'],
		queryFn: () => getPortalTasks(200),
	});

	const sections = useMemo(() => {
		const rows = q.data ?? [];
		const map = new Map<string, Record<string, unknown>[]>();
		for (const r of rows) {
			const k = dayKey(
				r.due_date as string | undefined,
				r.due_date_calendar as string | undefined,
			);
			if (!map.has(k)) map.set(k, []);
			map.get(k)!.push(r);
		}
		const keys = [...map.keys()].sort((a, b) => {
			if (a === 'Unscheduled') return 1;
			if (b === 'Unscheduled') return -1;
			return a.localeCompare(b);
		});
		return keys.map((key) => ({
			title: labelDay(key),
			data: map.get(key)!,
		}));
	}, [q.data]);

	return (
		<View style={styles.root}>
			<SectionList
				sections={sections}
				keyExtractor={(item) => String(item.name)}
				refreshControl={
					<RefreshControl refreshing={q.isFetching} onRefresh={() => void q.refetch()} tintColor={palette.accent} />
				}
				contentContainerStyle={styles.list}
				renderSectionHeader={({ section }) => (
					<Text style={styles.sectionHead}>{section.title}</Text>
				)}
				ListEmptyComponent={
					q.isLoading ? (
						<Text style={styles.muted}>Loading…</Text>
					) : (
						<Text style={styles.muted}>No tasks with due dates</Text>
					)
				}
				renderItem={({ item }) => (
					<Link href={`/task/${encodeURIComponent(String(item.name))}`} asChild>
						<Pressable style={styles.row}>
							<Text style={styles.subj} numberOfLines={2}>
								{String(item.subject ?? '')}
							</Text>
							<Text style={styles.meta}>{String(item.status ?? '')}</Text>
						</Pressable>
					</Link>
				)}
			/>
		</View>
	);
}

const styles = StyleSheet.create({
	root: { flex: 1, backgroundColor: palette.bg },
	list: { paddingBottom: 32 },
	sectionHead: {
		backgroundColor: palette.bg,
		paddingHorizontal: 16,
		paddingVertical: 10,
		fontSize: 12,
		fontWeight: '800',
		color: palette.accent,
		textTransform: 'uppercase',
		letterSpacing: 1,
	},
	row: {
		marginHorizontal: 16,
		marginBottom: 8,
		backgroundColor: palette.bgCard,
		borderRadius: 12,
		padding: 12,
		borderWidth: 1,
		borderColor: palette.border,
	},
	subj: { fontSize: 15, fontWeight: '600', color: palette.text },
	meta: { fontSize: 12, color: palette.textMuted, marginTop: 4 },
	muted: { color: palette.textMuted, textAlign: 'center', marginTop: 24 },
});
