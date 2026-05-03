import { type FormEvent, useState } from "react";
import { frappeWebPath, loginUrl, portalLogin } from "../api";

type Props = {
	onLoggedIn: () => void;
};

export default function LoginPage({ onLoggedIn }: Props) {
	const [usr, setUsr] = useState("");
	const [pwd, setPwd] = useState("");
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState<string | null>(null);

	async function onSubmit(e: FormEvent) {
		e.preventDefault();
		setError(null);
		setBusy(true);
		try {
			await portalLogin(usr.trim(), pwd);
			setPwd("");
			onLoggedIn();
		} catch (err) {
			setError(err instanceof Error ? err.message : "Sign in failed");
		} finally {
			setBusy(false);
		}
	}

	return (
		<div className="center-stage">
			<div className="card login-card login-form-card">
				<p className="eyebrow">Printechs Support</p>
				<h2 className="card-title">Sign in</h2>
				<p className="muted small">Use your portal account (website user).</p>

				<form className="login-form" onSubmit={onSubmit}>
					<label className="field">
						<span className="field-label">Email</span>
						<input
							className="field-input"
							type="email"
							autoComplete="username"
							value={usr}
							onChange={(e) => setUsr(e.target.value)}
							required
							disabled={busy}
						/>
					</label>
					<label className="field">
						<span className="field-label">Password</span>
						<input
							className="field-input"
							type="password"
							autoComplete="current-password"
							value={pwd}
							onChange={(e) => setPwd(e.target.value)}
							required
							disabled={busy}
						/>
					</label>
					{error ? <p className="error-text login-error">{error}</p> : null}
					<button className="btn-primary btn-block" type="submit" disabled={busy}>
						{busy ? "Signing in…" : "Sign in"}
					</button>
				</form>

				<p className="muted small login-alt">
					<a href={frappeWebPath("/login#forgot")}>Forgot password</a>
					{" · "}
					<a href={loginUrl()}>Open website login</a>
				</p>
			</div>
		</div>
	);
}
