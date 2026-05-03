import * as Clipboard from 'expo-clipboard';
import { useEffect, useState } from 'react';
import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { useAuth } from '@/context/AuthContext';
import { loadAuth } from '@/lib/session';
import { palette } from '@/constants/palette';

export default function MoreScreen() {
	const { bootstrap, logout, refreshBootstrap } = useAuth();
	const [url, setUrl] = useState<string | null>(null);

	useEffect(() => {
		void loadAuth().then((a) => setUrl(a?.baseUrl ?? null));
	}, []);

	async function copyUrl() {
		if (url) {
			await Clipboard.setStringAsync(url);
			Alert.alert('Copied', 'Site URL copied to clipboard.');
		}
	}

	return (
		<ScrollView style={styles.root} contentContainerStyle={styles.content}>
			<Text style={styles.h}>Account</Text>
			{bootstrap?.logged_in ? (
				<>
					<Text style={styles.row}>{bootstrap.full_name}</Text>
					<Text style={styles.muted}>{bootstrap.user}</Text>
					<Text style={styles.muted}>
						{bootstrap.internal ? 'Internal / management access' : 'Customer portal user'}
					</Text>
				</>
			) : null}

			<Text style={[styles.h, { marginTop: 28 }]}>Server</Text>
			<Pressable onPress={() => void copyUrl()}>
				<Text style={styles.url}>{url ?? '—'}</Text>
				<Text style={styles.tap}>Tap to copy URL</Text>
			</Pressable>

			<Pressable
				style={styles.secondary}
				onPress={() => {
					void refreshBootstrap();
					Alert.alert('Refreshed', 'Session refreshed.');
				}}>
				<Text style={styles.secondaryTxt}>Refresh session</Text>
			</Pressable>

			<Pressable
				style={styles.danger}
				onPress={() => {
					Alert.alert('Sign out', 'End this session on this device?', [
						{ text: 'Cancel', style: 'cancel' },
						{
							text: 'Sign out',
							style: 'destructive',
							onPress: () => void logout(),
						},
					]);
				}}>
				<Text style={styles.dangerTxt}>Sign out</Text>
			</Pressable>

			<Text style={styles.foot}>
				Printechs Support mobile · uses the same portal APIs as the web app. Use API Key login if password session is
				not available on your device.
			</Text>
		</ScrollView>
	);
}

const styles = StyleSheet.create({
	root: { flex: 1, backgroundColor: palette.bg },
	content: { padding: 20, paddingBottom: 48 },
	h: { fontSize: 12, fontWeight: '800', color: palette.textMuted, letterSpacing: 1, marginBottom: 12 },
	row: { fontSize: 18, fontWeight: '700', color: palette.text },
	muted: { fontSize: 14, color: palette.textMuted, marginTop: 4 },
	url: { fontSize: 14, color: palette.accent, fontWeight: '600' },
	tap: { fontSize: 12, color: palette.textMuted, marginTop: 4 },
	secondary: {
		marginTop: 20,
		padding: 14,
		borderRadius: 12,
		backgroundColor: palette.bgCard,
		borderWidth: 1,
		borderColor: palette.border,
		alignItems: 'center',
	},
	secondaryTxt: { color: palette.text, fontWeight: '600' },
	danger: {
		marginTop: 16,
		padding: 14,
		borderRadius: 12,
		backgroundColor: 'rgba(248,113,113,0.15)',
		alignItems: 'center',
	},
	dangerTxt: { color: palette.danger, fontWeight: '700' },
	foot: { marginTop: 32, fontSize: 12, color: palette.textMuted, lineHeight: 18 },
});
