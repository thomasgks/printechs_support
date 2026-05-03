import * as SecureStore from 'expo-secure-store';

const K_URL = 'printechs_frappe_url';
const K_TOKEN_KEY = 'printechs_api_key';
const K_TOKEN_SECRET = 'printechs_api_secret';
const K_COOKIE = 'printechs_cookie_header';
const K_CSRF = 'printechs_csrf';

export type StoredAuth =
	| { kind: 'token'; baseUrl: string; apiKey: string; apiSecret: string }
	| { kind: 'session'; baseUrl: string; cookieHeader: string; csrfToken: string };

export async function loadAuth(): Promise<StoredAuth | null> {
	const baseUrl = await SecureStore.getItemAsync(K_URL);
	if (!baseUrl) return null;

	const apiKey = await SecureStore.getItemAsync(K_TOKEN_KEY);
	const apiSecret = await SecureStore.getItemAsync(K_TOKEN_SECRET);
	if (apiKey && apiSecret) {
		return { kind: 'token', baseUrl, apiKey, apiSecret };
	}

	const cookieHeader = await SecureStore.getItemAsync(K_COOKIE);
	const csrf = await SecureStore.getItemAsync(K_CSRF);
	if (cookieHeader && csrf) {
		return { kind: 'session', baseUrl, cookieHeader, csrfToken: csrf };
	}

	return null;
}

export async function saveTokenAuth(baseUrl: string, apiKey: string, apiSecret: string) {
	await SecureStore.setItemAsync(K_URL, baseUrl);
	await SecureStore.setItemAsync(K_TOKEN_KEY, apiKey);
	await SecureStore.setItemAsync(K_TOKEN_SECRET, apiSecret);
	await SecureStore.deleteItemAsync(K_COOKIE).catch(() => {});
	await SecureStore.deleteItemAsync(K_CSRF).catch(() => {});
}

export async function saveSessionAuth(baseUrl: string, cookieHeader: string, csrfToken: string) {
	await SecureStore.setItemAsync(K_URL, baseUrl);
	await SecureStore.setItemAsync(K_COOKIE, cookieHeader);
	await SecureStore.setItemAsync(K_CSRF, csrfToken);
	await SecureStore.deleteItemAsync(K_TOKEN_KEY).catch(() => {});
	await SecureStore.deleteItemAsync(K_TOKEN_SECRET).catch(() => {});
}

export async function clearAuth() {
	await Promise.all([
		SecureStore.deleteItemAsync(K_URL).catch(() => {}),
		SecureStore.deleteItemAsync(K_TOKEN_KEY).catch(() => {}),
		SecureStore.deleteItemAsync(K_TOKEN_SECRET).catch(() => {}),
		SecureStore.deleteItemAsync(K_COOKIE).catch(() => {}),
		SecureStore.deleteItemAsync(K_CSRF).catch(() => {}),
	]);
}
