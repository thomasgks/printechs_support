import { Link } from "react-router-dom";

type Props = {
	title: string;
	subtitle?: string;
};

export default function PlaceholderPage({ title, subtitle }: Props) {
	return (
		<div className="max-w-2xl">
			<p className="mb-2 text-sm font-semibold uppercase tracking-wider text-violet-600">Printechs Support</p>
			<h1 className="mb-2 font-['Syne',system-ui,sans-serif] text-2xl font-extrabold tracking-tight text-slate-900">
				{title}
			</h1>
			<p className="mb-6 text-slate-600">
				{subtitle ??
					"This area is planned in the roadmap. Data will connect to ERPNext without breaking existing APIs."}
			</p>
			<div className="rounded-2xl border border-dashed border-slate-200 bg-white p-8 text-center shadow-saas">
				<p className="text-sm text-slate-500">Module placeholder — UI shell is live.</p>
				<p className="mt-4">
					<Link to="/" className="text-sm font-semibold text-violet-700 underline-offset-4 hover:underline">
						Back to dashboard
					</Link>
				</p>
			</div>
		</div>
	);
}
