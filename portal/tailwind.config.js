/** @type {import('tailwindcss').Config} */
export default {
	content: ["./index.html", "./src/**/*.{ts,tsx}"],
	important: "#root",
	corePlugins: { preflight: false },
	theme: {
		extend: {
			colors: {
				status: {
					new: "#64748b",
					open: "#2563eb",
					progress: "#4f46e5",
					waitcust: "#d97706",
					waitint: "#9333ea",
					done: "#16a34a",
					risk: "#dc2626",
				},
			},
			boxShadow: {
				saas: "0 4px 6px -1px rgb(15 23 42 / 0.06), 0 2px 4px -2px rgb(15 23 42 / 0.06)",
				"saas-lg": "0 20px 50px -12px rgb(15 23 42 / 0.12)",
			},
			borderRadius: {
				"4xl": "2rem",
			},
		},
	},
	plugins: [],
};
