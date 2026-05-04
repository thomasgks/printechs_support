import { type FormEvent, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { completePortalRegistration } from "../api";

export default function CompleteRegistrationPage() {
	const [searchParams] = useSearchParams();
	const navigate = useNavigate();
	const key = searchParams.get("key") || "";
	const [password, setPassword] = useState("");
	const [confirmPassword, setConfirmPassword] = useState("");
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [done, setDone] = useState(false);

	async function onSubmit(e: FormEvent) {
		e.preventDefault();
		setError(null);
		if (!key) {
			setError("Registration link is missing or invalid.");
			return;
		}
		if (password !== confirmPassword) {
			setError("Passwords do not match.");
			return;
		}
		setBusy(true);
		try {
			await completePortalRegistration(key, password);
			setPassword("");
			setConfirmPassword("");
			setDone(true);
			window.setTimeout(() => navigate("/", { replace: true }), 900);
		} catch (err) {
			setError(err instanceof Error ? err.message : "Could not complete registration");
		} finally {
			setBusy(false);
		}
	}

	return (
		<div className="center-stage">
			<div className="card login-card login-form-card">
				<p className="eyebrow">Printechs Support</p>
				<h2 className="card-title">Complete registration</h2>
				<p className="muted small">
					Set your password to activate your support portal account.
				</p>

				{done ? (
					<div className="success-box">
						<strong>Password set successfully.</strong>
						<span>Opening your support portal…</span>
					</div>
				) : (
					<form className="login-form" onSubmit={onSubmit}>
						<label className="field">
							<span className="field-label">New Password</span>
							<input
								className="field-input"
								type="password"
								autoComplete="new-password"
								value={password}
								onChange={(e) => setPassword(e.target.value)}
								required
								disabled={busy || !key}
							/>
						</label>
						<label className="field">
							<span className="field-label">Confirm Password</span>
							<input
								className="field-input"
								type="password"
								autoComplete="new-password"
								value={confirmPassword}
								onChange={(e) => setConfirmPassword(e.target.value)}
								required
								disabled={busy || !key}
							/>
						</label>
						{error ? <p className="error-text login-error">{error}</p> : null}
						<button className="btn-primary btn-block" type="submit" disabled={busy || !key}>
							{busy ? "Setting password…" : "Complete registration"}
						</button>
					</form>
				)}

				<p className="muted small login-alt">
					<Link to="/">Back to portal sign in</Link>
				</p>
			</div>
		</div>
	);
}
