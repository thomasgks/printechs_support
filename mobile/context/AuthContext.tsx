import { router } from 'expo-router';
import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import { clearAuth, loadAuth, type StoredAuth } from '@/lib/session';
import { loginWithApiKey, loginWithPassword } from '@/lib/frappe-api';
import { getPortalBootstrap, type PortalBootstrap } from '@/lib/portal';

type AuthState = {
	ready: boolean;
	auth: StoredAuth | null;
	bootstrap: PortalBootstrap | null;
	refreshBootstrap: () => Promise<void>;
	loginPassword: (baseUrl: string, email: string, password: string) => Promise<void>;
	loginApiKey: (baseUrl: string, apiKey: string, apiSecret: string) => Promise<void>;
	logout: () => Promise<void>;
};

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
	const [ready, setReady] = useState(false);
	const [auth, setAuth] = useState<StoredAuth | null>(null);
	const [bootstrap, setBootstrap] = useState<PortalBootstrap | null>(null);

	const refreshBootstrap = useCallback(async () => {
		const a = await loadAuth();
		setAuth(a);
		if (!a) {
			setBootstrap(null);
			return;
		}
		try {
			const b = await getPortalBootstrap();
			setBootstrap(b);
		} catch {
			setBootstrap(null);
			await clearAuth();
			setAuth(null);
		}
	}, []);

	useEffect(() => {
		let alive = true;
		(async () => {
			const a = await loadAuth();
			if (!alive) return;
			setAuth(a);
			if (a) {
				try {
					const b = await getPortalBootstrap();
					if (alive) setBootstrap(b);
				} catch {
					if (alive) {
						setBootstrap(null);
						await clearAuth();
						setAuth(null);
					}
				}
			}
			if (alive) setReady(true);
		})();
		return () => {
			alive = false;
		};
	}, []);

	const loginPassword = useCallback(async (baseUrl: string, email: string, password: string) => {
		await loginWithPassword(baseUrl, email, password);
		const a = await loadAuth();
		setAuth(a);
		const b = await getPortalBootstrap();
		setBootstrap(b);
	}, []);

	const loginApiKey = useCallback(async (baseUrl: string, apiKey: string, apiSecret: string) => {
		await loginWithApiKey(baseUrl, apiKey, apiSecret);
		const a = await loadAuth();
		setAuth(a);
		const b = await getPortalBootstrap();
		setBootstrap(b);
	}, []);

	const logout = useCallback(async () => {
		await clearAuth();
		setAuth(null);
		setBootstrap(null);
		router.replace('/login');
	}, []);

	const value = useMemo(
		() => ({
			ready,
			auth,
			bootstrap,
			refreshBootstrap,
			loginPassword,
			loginApiKey,
			logout,
		}),
		[ready, auth, bootstrap, refreshBootstrap, loginPassword, loginApiKey, logout],
	);

	return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth() {
	const v = useContext(Ctx);
	if (!v) throw new Error('useAuth outside AuthProvider');
	return v;
}
