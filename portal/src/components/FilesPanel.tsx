import { useCallback, useEffect, useRef, useState } from "react";
import {
	getPortalTaskFiles,
	getPortalTicketFiles,
	uploadPortalTaskFile,
	uploadPortalTicketFile,
	type PortalFileRow,
} from "../api";
import { formatFileSize } from "../lib/formatTime";

type Props = {
	mode: "ticket" | "task";
	name: string;
	title?: string;
	/** When true, hide upload UI (e.g. resolved ticket). */
	uploadDisabled?: boolean;
};

export default function FilesPanel({ mode, name, title, uploadDisabled }: Props) {
	const [rows, setRows] = useState<PortalFileRow[]>([]);
	const [loading, setLoading] = useState(true);
	const [uploading, setUploading] = useState(false);
	const [err, setErr] = useState<string | null>(null);
	const inputRef = useRef<HTMLInputElement>(null);

	const load = useCallback(async () => {
		setErr(null);
		setLoading(true);
		try {
			const list =
				mode === "ticket" ? await getPortalTicketFiles(name) : await getPortalTaskFiles(name);
			setRows(list);
		} catch (e) {
			setErr(e instanceof Error ? e.message : "Could not load files");
		} finally {
			setLoading(false);
		}
	}, [mode, name]);

	useEffect(() => {
		load();
	}, [load]);

	const onFiles = async (files: FileList | null) => {
		if (uploadDisabled) return;
		if (!files?.length) return;
		setUploading(true);
		setErr(null);
		try {
			for (let i = 0; i < files.length; i++) {
				const f = files[i];
				if (mode === "ticket") {
					await uploadPortalTicketFile(name, f);
				} else {
					await uploadPortalTaskFile(name, f);
				}
			}
			await load();
		} catch (e) {
			setErr(e instanceof Error ? e.message : "Upload failed");
		} finally {
			setUploading(false);
			if (inputRef.current) {
				inputRef.current.value = "";
			}
		}
	};

	const heading = title ?? (mode === "ticket" ? "Ticket attachments" : "Task attachments");

	return (
		<section className="overflow-hidden rounded-3xl border border-slate-200/90 bg-white shadow-[0_12px_40px_-12px_rgba(15,23,42,0.12)]">
			<div className="border-b border-slate-100 bg-gradient-to-r from-slate-50/80 to-white px-6 py-4">
				<h3 className="font-['Syne',system-ui,sans-serif] text-lg font-extrabold text-slate-900">{heading}</h3>
				<p className="text-xs text-slate-500">PDF, images, logs — stored on your ERPNext site.</p>
			</div>

			{uploadDisabled ? (
				<p className="mx-6 my-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950">
					Uploads are disabled while this ticket is resolved or closed. Reopen the ticket to add files.
				</p>
			) : null}

			<div
				className={`group relative mx-4 my-4 flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-slate-200 bg-slate-50/50 px-4 py-8 text-center transition sm:mx-6 ${
					uploadDisabled ? "pointer-events-none cursor-not-allowed opacity-50" : "cursor-pointer hover:border-violet-300 hover:bg-violet-50/30"
				}`}
				onDragOver={(e) => {
					if (uploadDisabled) return;
					e.preventDefault();
					e.stopPropagation();
				}}
				onDrop={(e) => {
					e.preventDefault();
					if (uploadDisabled) return;
					void onFiles(e.dataTransfer.files);
				}}
				onClick={() => {
					if (!uploadDisabled) inputRef.current?.click();
				}}
				role="presentation"
			>
				<input
					ref={inputRef}
					type="file"
					multiple
					className="hidden"
					disabled={uploadDisabled}
					onChange={(e) => void onFiles(e.target.files)}
				/>
				<div className="mb-2 flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-500 to-blue-700 text-white shadow-lg shadow-blue-500/30">
					<svg className="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
						<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12" strokeLinecap="round" strokeLinejoin="round" />
					</svg>
				</div>
				<p className="text-sm font-semibold text-slate-700">
					{uploading ? "Uploading…" : "Drop files here or click to upload"}
				</p>
				<p className="mt-1 text-xs text-slate-500">Multiple files supported</p>
			</div>

			{err ? <p className="px-6 pb-2 text-sm text-red-600">{err}</p> : null}

			<div className="border-t border-slate-100 px-4 pb-6 sm:px-6">
				{loading ? (
					<p className="py-4 text-center text-sm text-slate-500">Loading files…</p>
				) : rows.length === 0 ? (
					<p className="py-4 text-center text-sm text-slate-400">No attachments yet</p>
				) : (
					<ul className="space-y-2">
						{rows.map((f) => (
							<li
								key={f.name}
								className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-100 bg-slate-50/80 px-4 py-3 transition hover:border-violet-200 hover:bg-white"
							>
								<div className="min-w-0">
									<a
										href={f.file_url}
										className="font-semibold text-indigo-700 hover:underline"
										target="_blank"
										rel="noreferrer"
									>
										{f.file_name}
									</a>
									<p className="text-xs text-slate-500">
										{formatFileSize(f.file_size)} · {f.creation ?? ""}
									</p>
								</div>
								<span className="rounded-full bg-white px-2 py-1 text-[0.65rem] font-bold uppercase tracking-wide text-slate-500 ring-1 ring-slate-200">
									{f.owner ?? ""}
								</span>
							</li>
						))}
					</ul>
				)}
			</div>
		</section>
	);
}
