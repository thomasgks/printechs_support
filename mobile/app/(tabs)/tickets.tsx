import { useQuery } from '@tanstack/react-query';
import { Link } from 'expo-router';
import { FlatList, Pressable, RefreshControl, StyleSheet, Text, View } from 'react-native';

import { getPortalTickets } from '@/lib/portal';
import { palette } from '@/constants/palette';

export default function TicketsScreen() {
	const q = useQuery({
		queryKey: ['portal-tickets'],
		queryFn: () => getPortalTickets(80, { activeOnly: true }),
	});

	return (
		<View style={styles.root}>
			<FlatList
				data={q.data ?? []}
				keyExtractor={(item) => String(item.name)}
				refreshControl={
					<RefreshControl refreshing={q.isFetching} onRefresh={() => void q.refetch()} tintColor={palette.accent} />
				}
				contentContainerStyle={styles.list}
				ListEmptyComponent={
					q.isLoading ? (
						<Text style={styles.muted}>Loading…</Text>
					) : (
						<Text style={styles.muted}>No tickets</Text>
					)
				}
				renderItem={({ item }) => (
					<Link href={`/ticket/${encodeURIComponent(String(item.name))}`} asChild>
						<Pressable style={styles.row}>
							<View style={styles.rowTop}>
								<Text style={styles.name}>{String(item.name)}</Text>
								<Text style={styles.status}>{String(item.status ?? '')}</Text>
							</View>
							<Text style={styles.subj} numberOfLines={2}>
								{String(item.subject ?? '')}
							</Text>
							{item.customer ? (
								<Text style={styles.cust} numberOfLines={1}>
									{String(item.customer)}
								</Text>
							) : null}
						</Pressable>
					</Link>
				)}
			/>
		</View>
	);
}

const styles = StyleSheet.create({
	root: { flex: 1, backgroundColor: palette.bg },
	list: { padding: 16, paddingBottom: 32 },
	row: {
		backgroundColor: palette.bgCard,
		borderRadius: 14,
		padding: 14,
		marginBottom: 10,
		borderWidth: 1,
		borderColor: palette.border,
	},
	rowTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 },
	name: { fontSize: 13, fontWeight: '700', color: palette.accent },
	status: { fontSize: 12, color: palette.textMuted, fontWeight: '600' },
	subj: { fontSize: 16, fontWeight: '600', color: palette.text },
	cust: { fontSize: 13, color: palette.textMuted, marginTop: 6 },
	muted: { color: palette.textMuted, textAlign: 'center', marginTop: 24 },
});
