/// <reference types="vite/client" />

interface ImportMetaEnv {
	readonly VITE_FRAPPE_SITE_URL?: string;
	/** When "true", bootstrap/tickets/tasks use fixtures in portalMock.ts (no Frappe API). */
	readonly VITE_PORTAL_USE_MOCK_DATA?: string;
}

interface ImportMeta {
	readonly env: ImportMetaEnv;
}
