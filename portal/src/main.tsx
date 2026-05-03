import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import "./index.css";

const basename = import.meta.env.DEV ? "/" : "/support-portal";

const el = document.getElementById("root");
if (el) {
	createRoot(el).render(
		<StrictMode>
			<BrowserRouter basename={basename}>
				<App />
			</BrowserRouter>
		</StrictMode>,
	);
}
