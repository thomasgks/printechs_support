import Constants from 'expo-constants';

/** HTTPS base URL of the Frappe site, no trailing slash (e.g. https://erp.example.com). */
export function getFrappeBaseUrl(): string {
	const env = process.env.EXPO_PUBLIC_FRAPPE_URL;
	if (typeof env === 'string' && env.trim()) {
		return env.replace(/\/$/, '');
	}
	const extra = Constants.expoConfig?.extra as { frappeUrl?: string } | undefined;
	if (extra?.frappeUrl) {
		return String(extra.frappeUrl).replace(/\/$/, '');
	}
	return '';
}
