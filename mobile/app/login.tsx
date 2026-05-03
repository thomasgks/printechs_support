import { useRouter } from 'expo-router';
import { useState } from 'react';
import {
	ActivityIndicator,
	KeyboardAvoidingView,
	Platform,
	Pressable,
	ScrollView,
	StyleSheet,
	Text,
	TextInput,
	View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useAuth } from '@/context/AuthContext';
import { getFrappeBaseUrl } from '@/lib/config';
import { palette } from '@/constants/palette';

export default function LoginScreen() {
	const router = useRouter();
	const insets = useSafeAreaInsets();
	const { loginPassword, loginApiKey } = useAuth();

	const [baseUrl, setBaseUrl] = useState(getFrappeBaseUrl());
	const [email, setEmail] = useState('');
	const [password, setPassword] = useState('');
	const [apiKey, setApiKey] = useState('');
	const [apiSecret, setApiSecret] = useState('');
	const [mode, setMode] = useState<'password' | 'apikey'>('password');
	const [loading, setLoading] = useState(false);
	const [err, setErr] = useState<string | null>(null);

	async function onSubmit() {
		setErr(null);
		const url = baseUrl.trim().replace(/\/$/, '');
		if (!url.startsWith('https://')) {
			setErr('Use a full HTTPS URL (e.g. https://erp.yourcompany.com).');
			return;
		}
		setLoading(true);
		try {
			if (mode === 'password') {
				if (!email.trim() || !password) {
					setErr('Email and password are required.');
					return;
				}
				await loginPassword(url, email.trim(), password);
			} else {
				if (!apiKey.trim() || !apiSecret.trim()) {
					setErr('API Key and API Secret are required.');
					return;
				}
				await loginApiKey(url, apiKey.trim(), apiSecret.trim());
			}
			router.replace('/(tabs)');
		} catch (e) {
			setErr(e instanceof Error ? e.message : 'Sign in failed');
		} finally {
			setLoading(false);
		}
	}

	return (
		<KeyboardAvoidingView
			style={[styles.root, { paddingTop: insets.top }]}
			behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
			<ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
				<Text style={styles.logo}>Printechs</Text>
				<Text style={styles.title}>Support</Text>
				<Text style={styles.sub}>Sign in to your ERPNext site</Text>

				<Text style={styles.label}>Site URL</Text>
				<TextInput
					style={styles.input}
					placeholder="https://your-site.com"
					placeholderTextColor={palette.textMuted}
					autoCapitalize="none"
					autoCorrect={false}
					value={baseUrl}
					onChangeText={setBaseUrl}
				/>

				<View style={styles.modeRow}>
					<Pressable onPress={() => setMode('password')} style={[styles.modeBtn, mode === 'password' && styles.modeBtnOn]}>
						<Text style={[styles.modeTxt, mode === 'password' && styles.modeTxtOn]}>Email</Text>
					</Pressable>
					<Pressable onPress={() => setMode('apikey')} style={[styles.modeBtn, mode === 'apikey' && styles.modeBtnOn]}>
						<Text style={[styles.modeTxt, mode === 'apikey' && styles.modeTxtOn]}>API Key</Text>
					</Pressable>
				</View>

				{mode === 'password' ? (
					<>
						<Text style={styles.label}>Email</Text>
						<TextInput
							style={styles.input}
							placeholder="you@company.com"
							placeholderTextColor={palette.textMuted}
							autoCapitalize="none"
							keyboardType="email-address"
							value={email}
							onChangeText={setEmail}
						/>
						<Text style={styles.label}>Password</Text>
						<TextInput
							style={styles.input}
							placeholder="••••••••"
							placeholderTextColor={palette.textMuted}
							secureTextEntry
							value={password}
							onChangeText={setPassword}
						/>
					</>
				) : (
					<>
						<Text style={styles.hint}>
							Desk → User → Settings → API Access → Generate Keys. Use the key as API Key and the secret as API Secret.
						</Text>
						<Text style={styles.label}>API Key</Text>
						<TextInput
							style={styles.input}
							placeholder="xxxxxxxx"
							placeholderTextColor={palette.textMuted}
							autoCapitalize="none"
							value={apiKey}
							onChangeText={setApiKey}
						/>
						<Text style={styles.label}>API Secret</Text>
						<TextInput
							style={styles.input}
							placeholder="••••••••"
							placeholderTextColor={palette.textMuted}
							secureTextEntry
							value={apiSecret}
							onChangeText={setApiSecret}
						/>
					</>
				)}

				{err ? <Text style={styles.err}>{err}</Text> : null}

				<Pressable style={styles.primary} onPress={() => void onSubmit()} disabled={loading}>
					{loading ? (
						<ActivityIndicator color="#fff" />
					) : (
						<Text style={styles.primaryTxt}>Continue</Text>
					)}
				</Pressable>
			</ScrollView>
		</KeyboardAvoidingView>
	);
}

const styles = StyleSheet.create({
	root: {
		flex: 1,
		backgroundColor: palette.bg,
	},
	scroll: {
		padding: 24,
		paddingBottom: 48,
	},
	logo: {
		fontSize: 14,
		fontWeight: '700',
		color: palette.accent,
		letterSpacing: 3,
		textTransform: 'uppercase',
	},
	title: {
		fontSize: 36,
		fontWeight: '800',
		color: palette.text,
		marginTop: 4,
		letterSpacing: -1,
	},
	sub: {
		fontSize: 15,
		color: palette.textMuted,
		marginTop: 8,
		marginBottom: 28,
	},
	label: {
		fontSize: 12,
		fontWeight: '600',
		color: palette.textMuted,
		marginBottom: 6,
		textTransform: 'uppercase',
		letterSpacing: 0.5,
	},
	input: {
		backgroundColor: palette.bgCard,
		borderWidth: 1,
		borderColor: palette.border,
		borderRadius: 12,
		paddingHorizontal: 16,
		paddingVertical: 14,
		fontSize: 16,
		color: palette.text,
		marginBottom: 16,
	},
	modeRow: {
		flexDirection: 'row',
		gap: 8,
		marginBottom: 16,
	},
	modeBtn: {
		flex: 1,
		paddingVertical: 10,
		borderRadius: 10,
		backgroundColor: palette.bgCard,
		borderWidth: 1,
		borderColor: palette.border,
		alignItems: 'center',
	},
	modeBtnOn: {
		borderColor: palette.accent,
		backgroundColor: palette.bgElevated,
	},
	modeTxt: {
		color: palette.textMuted,
		fontWeight: '600',
	},
	modeTxtOn: {
		color: palette.accent,
	},
	hint: {
		fontSize: 13,
		color: palette.textMuted,
		lineHeight: 20,
		marginBottom: 12,
	},
	err: {
		color: palette.danger,
		marginBottom: 12,
		fontSize: 14,
	},
	primary: {
		backgroundColor: palette.accent,
		borderRadius: 14,
		paddingVertical: 16,
		alignItems: 'center',
		marginTop: 8,
	},
	primaryTxt: {
		color: '#0c1222',
		fontSize: 17,
		fontWeight: '700',
	},
});
