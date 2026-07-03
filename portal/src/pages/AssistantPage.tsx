import { FormEvent, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
	escalatePraiToTicket,
	getPortalBootstrap,
	portalTicketPath,
	praiAsk,
	type PortalBootstrapResult,
	type PraiChatMessage,
	type PraiChatSession,
} from "../api";

const STARTER_PROMPTS = [
	"How to set up a cashier in ERPNext?",
	"How do I set up a promotion in Modern POS?",
	"Barcode scanner not working on POS",
	"Loyalty points not applying at checkout",
	"How to sync Modern POS with ERPNext?",
	"How do I create a support ticket?",
];

function SourceLinks({ sources }: { sources: PraiChatMessage["sources"] }) {
	if (!sources?.length) return null;
	return (
		<div className="mt-2 flex flex-wrap gap-2">
			{sources.map((source) => {
				const href =
					source.type === "ticket" && source.name
						? portalTicketPath(source.name)
						: source.url || (source.name ? `/help-center?article=${encodeURIComponent(source.name)}` : "");
				if (!href) return null;
				const external = href.startsWith("http");
				return external ? (
					<a
						key={`${source.type}-${source.name}`}
						href={href}
						target="_blank"
						rel="noopener noreferrer"
						className="inline-flex items-center rounded-lg border border-violet-200 bg-white px-2 py-1 text-[11px] font-semibold text-violet-700 hover:bg-violet-50"
					>
						{source.title}
					</a>
				) : (
					<Link
						key={`${source.type}-${source.name}`}
						to={href}
						className="inline-flex items-center rounded-lg border border-violet-200 bg-white px-2 py-1 text-[11px] font-semibold text-violet-700 hover:bg-violet-50"
					>
						{source.title}
					</Link>
				);
			})}
		</div>
	);
}

function formatStepLabel(line: string): { label: string; body: string } | null {
	const match = line.match(/^(.+?)\s*[—–-]\s*(.+)$/);
	if (!match) return null;
	return { label: match[1].trim(), body: match[2].trim() };
}

function ChatMessageContent({ content }: { content: string }) {
	const blocks = content.split(/\n\n+/).filter((block) => block.trim());

	return (
		<div className="space-y-3">
			{blocks.map((block, blockIndex) => {
				const lines = block
					.split("\n")
					.map((line) => line.trim())
					.filter(Boolean);
				const numbered = lines.length > 0 && lines.every((line) => /^\d+\.\s/.test(line));
				const bullets = lines.length > 0 && lines.every((line) => /^[•-]\s/.test(line));

				if (numbered) {
					return (
						<ol key={blockIndex} className="space-y-3">
							{lines.map((line, lineIndex) => {
								const text = line.replace(/^\d+\.\s*/, "");
								const step = formatStepLabel(text);
								return (
									<li key={lineIndex} className="flex gap-3">
										<span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-violet-100 text-xs font-bold text-violet-700">
											{lineIndex + 1}
										</span>
										<div className="min-w-0">
											{step ? (
												<>
													<p className="font-semibold text-slate-900">{step.label}</p>
													<p className="mt-1 text-slate-700">{step.body}</p>
												</>
											) : (
												<p className="text-slate-700">{text}</p>
											)}
										</div>
									</li>
								);
							})}
						</ol>
					);
				}

				if (bullets) {
					return (
						<ul key={blockIndex} className="list-disc space-y-2 pl-5 text-slate-700">
							{lines.map((line, lineIndex) => (
								<li key={lineIndex}>{line.replace(/^[•-]\s*/, "")}</li>
							))}
						</ul>
					);
				}

				return (
					<p key={blockIndex} className="whitespace-pre-wrap text-slate-700">
						{block}
					</p>
				);
			})}
		</div>
	);
}

function MessageBubble({ message }: { message: PraiChatMessage }) {
	const isUser = message.role === "User";
	return (
		<div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
			<div
				className={`max-w-[min(100%,42rem)] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm ${
					isUser
						? "bg-gradient-to-br from-violet-600 to-indigo-600 text-white"
						: "border border-slate-200 bg-white text-slate-800"
				}`}
			>
				{isUser ? (
					<p className="whitespace-pre-wrap">{message.content}</p>
				) : (
					<ChatMessageContent content={message.content} />
				)}
				{!isUser ? <SourceLinks sources={message.sources} /> : null}
			</div>
		</div>
	);
}

export default function AssistantPage() {
	const [bootstrap, setBootstrap] = useState<Extract<PortalBootstrapResult, { logged_in: true }> | null>(null);
	const [session, setSession] = useState<PraiChatSession | null>(null);
	const [input, setInput] = useState("");
	const [loading, setLoading] = useState(false);
	const [escalating, setEscalating] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [suggestEscalation, setSuggestEscalation] = useState(false);
	const bottomRef = useRef<HTMLDivElement | null>(null);

	useEffect(() => {
		getPortalBootstrap().then((b) => {
			if (b.logged_in) setBootstrap(b);
		});
	}, []);

	useEffect(() => {
		bottomRef.current?.scrollIntoView({ behavior: "smooth" });
	}, [session?.messages?.length, loading]);

	async function sendMessage(text: string) {
		const message = text.trim();
		if (!message || loading) return;
		setError(null);
		setLoading(true);
		setInput("");
		try {
			const result = await praiAsk(message, session?.name);
			setSession(result.session);
			setSuggestEscalation(Boolean(result.suggest_escalation));
		} catch (e) {
			setError(e instanceof Error ? e.message : "Could not send message");
			setInput(message);
		} finally {
			setLoading(false);
		}
	}

	async function onSubmit(e: FormEvent) {
		e.preventDefault();
		await sendMessage(input);
	}

	async function onEscalate() {
		if (!session?.name || escalating || session.support_ticket) return;
		setEscalating(true);
		setError(null);
		try {
			const result = await escalatePraiToTicket(session.name);
			setSession(result.session);
			setSuggestEscalation(false);
		} catch (e) {
			setError(e instanceof Error ? e.message : "Could not create ticket");
		} finally {
			setEscalating(false);
		}
	}

	const messages = session?.messages ?? [];
	const linkedTicket = session?.support_ticket?.trim();

	return (
		<div className="flex h-[calc(100vh-8rem)] min-h-[32rem] flex-col">
			<div className="mb-4 flex flex-wrap items-start justify-between gap-3">
				<div>
					<p className="mb-1 text-sm font-semibold uppercase tracking-wider text-violet-600">PRAI</p>
					<h1 className="font-['Syne',system-ui,sans-serif] text-2xl font-extrabold tracking-tight text-slate-900">
						Printechs Retail AI Assistant
					</h1>
					<p className="mt-1 max-w-2xl text-sm text-slate-600">
						{bootstrap?.prai_openai_enabled
							? "Verified FAQ answers first, then structured AI guidance for any retail or ERPNext question."
							: "Answers from verified PRAI FAQ and Help Center. Enable AI Chat Answers in Printechs Support Settings for broader questions."}
					</p>
				</div>
				<div className="flex flex-wrap gap-2">
					{bootstrap?.help_url ? (
						<a
							href={bootstrap.help_url}
							target="_blank"
							rel="noopener noreferrer"
							className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 shadow-sm hover:border-violet-200 hover:text-violet-700"
						>
							Help Center
						</a>
					) : null}
					{linkedTicket ? (
						<Link
							to={portalTicketPath(linkedTicket)}
							className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-800 shadow-sm hover:bg-emerald-100"
						>
							View ticket {linkedTicket}
						</Link>
					) : null}
				</div>
			</div>

			<section className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-saas">
				<div className="flex-1 space-y-4 overflow-y-auto px-4 py-5 md:px-6">
					{messages.length === 0 ? (
						<div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/80 p-6 text-center">
							<p className="text-sm text-slate-600">
								Ask about Modern POS, promotions, stock, loyalty, ERPNext, or support portal tasks.
							</p>
							<div className="mt-4 flex flex-wrap justify-center gap-2">
								{STARTER_PROMPTS.map((prompt) => (
									<button
										key={prompt}
										type="button"
										onClick={() => sendMessage(prompt)}
										disabled={loading}
										className="rounded-full border border-violet-200 bg-white px-3 py-1.5 text-xs font-semibold text-violet-700 hover:bg-violet-50 disabled:opacity-60"
									>
										{prompt}
									</button>
								))}
							</div>
						</div>
					) : (
						messages.map((message) => <MessageBubble key={message.name || `${message.role}-${message.created_at}`} message={message} />)
					)}
					{loading ? (
						<div className="flex justify-start">
							<div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-500">
								PRAI is thinking…
							</div>
						</div>
					) : null}
					<div ref={bottomRef} />
				</div>

				<div className="border-t border-slate-200 bg-slate-50/70 px-4 py-4 md:px-6">
					{error ? <p className="mb-3 text-sm font-medium text-red-600">{error}</p> : null}
					{suggestEscalation && !linkedTicket ? (
						<div className="mb-3 flex flex-wrap items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
							<span>No close match found.</span>
							<button
								type="button"
								onClick={onEscalate}
								disabled={escalating || !session?.name}
								className="rounded-lg bg-amber-600 px-3 py-1 text-xs font-semibold text-white hover:bg-amber-700 disabled:opacity-60"
							>
								{escalating ? "Creating ticket…" : "Create support ticket"}
							</button>
						</div>
					) : null}
					<form onSubmit={onSubmit} className="flex flex-wrap items-end gap-2">
						<label className="min-w-[min(100%,20rem)] flex-1">
							<span className="sr-only">Your question</span>
							<textarea
								value={input}
								onChange={(e) => setInput(e.target.value)}
								rows={2}
								placeholder="Type your question…"
								className="w-full resize-none rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 shadow-sm outline-none ring-violet-200 focus:ring-2"
								disabled={loading}
							/>
						</label>
						<div className="flex gap-2">
							{session?.name && !linkedTicket ? (
								<button
									type="button"
									onClick={onEscalate}
									disabled={escalating || loading}
									className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:border-violet-200 hover:text-violet-700 disabled:opacity-60"
								>
									{escalating ? "Creating…" : "Create ticket"}
								</button>
							) : null}
							<button
								type="submit"
								disabled={loading || !input.trim()}
								className="rounded-xl bg-violet-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-violet-700 disabled:cursor-not-allowed disabled:opacity-60"
							>
								{loading ? "Sending…" : "Send"}
							</button>
						</div>
					</form>
				</div>
			</section>
		</div>
	);
}
