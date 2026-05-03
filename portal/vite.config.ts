import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const outDir = path.resolve(__dirname, "../printechs_support/public/portal");

export default defineConfig(({ mode }) => ({
	plugins: [react()],
	base: mode === "development" ? "/" : "/assets/printechs_support/portal/",
	resolve: {
		alias: { "@": path.resolve(__dirname, "src") },
	},
	build: {
		outDir,
		emptyOutDir: true,
		// Hashed filenames so browsers load new builds after deploy (fixed "index.js" was cached forever).
		rollupOptions: {
			output: {
				entryFileNames: "assets/[name]-[hash].js",
				chunkFileNames: "assets/[name]-[hash].js",
				assetFileNames: "assets/[name]-[hash][extname]",
			},
		},
	},
	server: {
		port: 5173,
		proxy: {
			"/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
			"/assets": { target: "http://127.0.0.1:8000", changeOrigin: true },
		},
	},
}));
