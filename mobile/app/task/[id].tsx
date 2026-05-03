import { useQuery } from '@tanstack/react-query';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, Pressable, View } from 'react-native';

import { getPortalTask } from '@/lib/portal';
import { formatPortalDueCalendar } from '@/lib/portalDates';
import { palette } from '@/constants/palette';

function stripHtml(html: string): string {
	return html.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
}

export default function TaskDetailScreen() {
	const { id } = useLocalSearchParams<{ id: string }>();
	const router = useRouter();
	const name = decodeURIComponent(id ?? '');

	const q = useQuery({
		queryKey: ['task', name],
		queryFn: () => getPortalTask(name),
		enabled: !!name,
	});

	const doc = q.data;

	return (
		<ScrollView
			style={styles.root}
			contentContainerStyle={styles.content}
			refreshControl={
				<RefreshControl refreshing={q.isFetching} onRefresh={() => void q.refetch()} tintColor={palette.accent} />
			}>
			{q.isLoading ? (
				<ActivityIndicator color={palette.accent} style={{ marginTop: 24 }} />
			) : q.isError ? (
				<Text style={styles.err}>{q.error instanceof Error ? q.error.message : 'Error'}</Text>
			) : doc ? (
				<>
					<Text style={styles.title}>{String(doc.subject ?? '')}</Text>
					<Text style={styles.meta}>
						{String(doc.name)} · {String(doc.status ?? '')}
					</Text>
					{doc.due_date || doc.due_date_calendar ? (
						<Text style={styles.due}>Due {formatPortalDueCalendar(doc as Record<string, unknown>)}</Text>
					) : null}
					{doc.description ? (
						<Text style={styles.body}>{stripHtml(String(doc.description))}</Text>
					) : null}
				</>
			) : null}
			<Pressable style={styles.back} onPress={() => router.back()}>
				<Text style={styles.backTxt}>← Back</Text>
			</Pressable>
		</ScrollView>
	);
}

const styles = StyleSheet.create({
	root: { flex: 1, backgroundColor: palette.bg },
	content: { padding: 16, paddingBottom: 40 },
	title: { fontSize: 22, fontWeight: '800', color: palette.text },
	meta: { fontSize: 13, color: palette.textMuted, marginTop: 8 },
	due: { fontSize: 14, color: palette.warning, fontWeight: '700', marginTop: 10 },
	body: { fontSize: 15, lineHeight: 22, color: palette.text, marginTop: 16 },
	back: { marginTop: 24 },
	backTxt: { color: palette.textMuted, fontWeight: '600' },
	err: { color: palette.danger },
});
