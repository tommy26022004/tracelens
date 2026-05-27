<script lang="ts">
	import { analyseApplication, fetchChunk } from '$lib/api';
	import CitedText from '$lib/components/CitedText.svelte';
	import ChunkModal from '$lib/components/ChunkModal.svelte';
	import type { AnalysisResponse, ChunkDetail, Rating } from '$lib/types';

	let files: File[] = $state([]);
	let dragging = $state(false);
	let analysing = $state(false);
	let result: AnalysisResponse | null = $state(null);
	let analyseError: string | null = $state(null);

	let activeChunkId: string | null = $state(null);
	let activeChunk: ChunkDetail | null = $state(null);
	let chunkLoading = $state(false);
	let chunkError: string | null = $state(null);

	const dimensionOrder = ['character', 'capacity', 'capital', 'collateral', 'conditions'] as const;

	function onFileChange(event: Event) {
		const input = event.target as HTMLInputElement;
		files = input.files ? Array.from(input.files) : [];
	}

	function onDrop(event: DragEvent) {
		event.preventDefault();
		dragging = false;
		const dropped = event.dataTransfer?.files;
		if (dropped) {
			files = Array.from(dropped).filter((f) => f.name.toLowerCase().endsWith('.pdf'));
		}
	}

	async function submit() {
		if (files.length === 0) return;
		analysing = true;
		analyseError = null;
		result = null;
		try {
			result = await analyseApplication(files);
		} catch (err) {
			analyseError = err instanceof Error ? err.message : String(err);
		} finally {
			analysing = false;
		}
	}

	async function openChunk(chunkId: string) {
		activeChunkId = chunkId;
		activeChunk = null;
		chunkError = null;
		chunkLoading = true;
		try {
			activeChunk = await fetchChunk(chunkId);
		} catch (err) {
			chunkError = err instanceof Error ? err.message : String(err);
		} finally {
			chunkLoading = false;
		}
	}

	function closeChunk() {
		activeChunkId = null;
		activeChunk = null;
		chunkError = null;
	}

	function ratingClass(rating: Rating): string {
		return `rating-${rating}`;
	}
</script>

<section class="space-y-6">
	<!-- Upload card -->
	<div class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
		<h2 class="text-base font-semibold text-slate-900">Upload SME application package</h2>
		<p class="mt-1 text-sm text-slate-500">
			Drag in or pick the bank statements, SSM registration, and other supporting PDFs. The agent
			will run all six steps and return a source-traced summary.
		</p>

		<div
			class="mt-4 flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-300 p-8 text-center transition-colors"
			class:bg-indigo-50={dragging}
			class:border-indigo-300={dragging}
			ondragover={(e) => {
				e.preventDefault();
				dragging = true;
			}}
			ondragleave={() => (dragging = false)}
			ondrop={onDrop}
			role="region"
			aria-label="Drop zone"
		>
			<svg
				class="h-10 w-10 text-slate-400"
				fill="none"
				stroke="currentColor"
				stroke-width="1.5"
				viewBox="0 0 24 24"
			>
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					d="M12 16.5V9.75m0 0 3 3m-3-3-3 3M6.75 19.5h10.5A2.25 2.25 0 0 0 19.5 17.25v-1.5"
				/>
			</svg>
			<p class="mt-2 text-sm text-slate-600">Drop PDFs here, or</p>
			<label class="mt-2 cursor-pointer text-sm font-medium text-indigo-600 hover:text-indigo-500">
				<input
					type="file"
					accept="application/pdf"
					multiple
					class="hidden"
					onchange={onFileChange}
				/>
				browse to select
			</label>
		</div>

		{#if files.length > 0}
			<ul class="mt-4 space-y-1 text-sm text-slate-700">
				{#each files as file (file.name)}
					<li class="flex items-center gap-2">
						<span class="text-slate-400">·</span>
						<span class="font-medium">{file.name}</span>
						<span class="text-xs text-slate-400">{(file.size / 1024).toFixed(1)} KB</span>
					</li>
				{/each}
			</ul>
		{/if}

		<button
			type="button"
			class="mt-4 inline-flex items-center rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-500 disabled:cursor-not-allowed disabled:bg-slate-300"
			disabled={files.length === 0 || analysing}
			onclick={submit}
		>
			{#if analysing}
				<svg class="mr-2 h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
					<circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" opacity="0.25" />
					<path
						d="M22 12a10 10 0 0 1-10 10"
						stroke="currentColor"
						stroke-width="3"
						stroke-linecap="round"
					/>
				</svg>
				Analysing…
			{:else}
				Analyse package
			{/if}
		</button>

		{#if analyseError}
			<p class="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
				{analyseError}
			</p>
		{/if}
	</div>

	{#if result}
		<!-- Risk summary card -->
		{#if result.risk_summary}
			<div class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
				<h2 class="text-base font-semibold text-slate-900">Risk summary</h2>
				<p class="mt-1 text-xs text-slate-500">
					Citations are inline. Click any tag to view the source PDF row.
				</p>

				<p class="mt-4 text-lg leading-snug font-medium text-slate-900">
					<CitedText text={result.risk_summary.headline} onCitationClick={openChunk} />
				</p>
				<p class="mt-3 text-sm leading-relaxed text-slate-700">
					<CitedText text={result.risk_summary.body} onCitationClick={openChunk} />
				</p>

				{#if result.risk_summary.recommended_human_checks.length > 0}
					<div class="mt-4 border-t border-slate-100 pt-4">
						<h3 class="text-xs font-medium tracking-wide text-slate-500 uppercase">
							Recommended human checks
						</h3>
						<ul class="mt-2 space-y-1 text-sm text-slate-700">
							{#each result.risk_summary.recommended_human_checks as check (check)}
								<li class="flex gap-2"><span class="text-amber-500">⚑</span>{check}</li>
							{/each}
						</ul>
					</div>
				{/if}
			</div>
		{/if}

		<!-- 5C grid -->
		{#if result.five_c && 'character' in result.five_c}
			<div class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
				<h2 class="text-base font-semibold text-slate-900">5C credit assessment</h2>
				<div class="mt-4 grid gap-3 md:grid-cols-5">
					{#each dimensionOrder as key (key)}
						{@const dim = result.five_c[key]}
						<div class="rounded-lg border border-slate-200 p-4">
							<p class="text-xs font-medium tracking-wide text-slate-500 uppercase">
								{dim.name}
							</p>
							<span
								class="mt-1 inline-block rounded-full px-2 py-0.5 text-xs font-medium {ratingClass(
									dim.rating
								)}"
							>
								{dim.rating.replace('_', ' ')}
							</span>
							<p class="mt-2 text-xs leading-relaxed text-slate-700">{dim.reasoning}</p>
							{#if dim.evidence_chunk_ids.length > 0}
								<div class="mt-2 flex flex-wrap gap-1">
									{#each dim.evidence_chunk_ids as cid (cid)}
										<button
											type="button"
											class="citation"
											title={cid}
											onclick={() => openChunk(cid)}
										>
											{cid.split(':').slice(-2).join(':')}
										</button>
									{/each}
								</div>
							{/if}
						</div>
					{/each}
				</div>
			</div>
		{/if}

		<!-- Inconsistencies -->
		{#if result.inconsistencies.length > 0}
			<div class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
				<h2 class="text-base font-semibold text-slate-900">
					Validation findings ({result.inconsistencies.length})
				</h2>
				<ul class="mt-3 space-y-2">
					{#each result.inconsistencies as issue (issue.code + issue.message)}
						<li class="rounded-md border px-3 py-2 text-sm severity-{issue.severity}">
							<div class="flex items-baseline gap-2">
								<span class="text-xs font-semibold uppercase">{issue.severity}</span>
								<span class="font-mono text-xs">{issue.code}</span>
							</div>
							<p class="mt-1">{issue.message}</p>
							{#if issue.citations.length > 0}
								<div class="mt-1 flex flex-wrap gap-1">
									{#each issue.citations as cid (cid)}
										<button type="button" class="citation" onclick={() => openChunk(cid)}>
											{cid.split(':').slice(-2).join(':')}
										</button>
									{/each}
								</div>
							{/if}
						</li>
					{/each}
				</ul>
			</div>
		{/if}

		<!-- Metrics + Trace side-by-side on wide -->
		<div class="grid gap-6 md:grid-cols-2">
			{#if result.ratios?.bank_statement_metrics?.length}
				<div class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
					<h2 class="text-base font-semibold text-slate-900">Bank-statement metrics</h2>
					{#each result.ratios.bank_statement_metrics as m (m.document_id)}
						<dl class="mt-3 grid grid-cols-2 gap-y-1 text-sm">
							<dt class="text-slate-500">Document</dt>
							<dd class="font-mono text-xs text-slate-700 break-all">{m.document_id}</dd>
							<dt class="text-slate-500">Net change</dt>
							<dd class="text-slate-900">RM {m.net_change}</dd>
							<dt class="text-slate-500">Avg daily inflow</dt>
							<dd class="text-slate-900">RM {m.avg_daily_inflow}</dd>
							<dt class="text-slate-500">Avg daily outflow</dt>
							<dd class="text-slate-900">RM {m.avg_daily_outflow}</dd>
							<dt class="text-slate-500">Deposits / Withdrawals</dt>
							<dd class="text-slate-900">{m.deposit_count} / {m.withdrawal_count}</dd>
							<dt class="text-slate-500">Closing balance</dt>
							<dd class="text-slate-900">RM {m.end_of_period_balance}</dd>
						</dl>
					{/each}
				</div>
			{/if}

			<div class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
				<h2 class="text-base font-semibold text-slate-900">Reasoning trail</h2>
				<ol class="mt-3 space-y-2 text-sm">
					{#each result.trace as step, i (i)}
						<li class="flex items-start gap-3">
							<span class="mt-0.5 font-mono text-xs text-slate-400">
								{step.duration_ms.toFixed(0)}ms
							</span>
							<div>
								<p class="font-medium text-slate-800">{step.node}</p>
								<p class="text-xs text-slate-500">{step.summary}</p>
							</div>
						</li>
					{/each}
				</ol>
				{#if result.errors.length > 0}
					<div class="mt-3 border-t border-slate-100 pt-3">
						<p class="text-xs font-medium tracking-wide text-amber-700 uppercase">
							Recoverable errors
						</p>
						<ul class="mt-1 space-y-1 text-xs text-amber-700">
							{#each result.errors as err (err.message)}
								<li>[{err.node}] {err.message}</li>
							{/each}
						</ul>
					</div>
				{/if}
			</div>
		</div>
	{/if}
</section>

<ChunkModal
	chunkId={activeChunkId}
	chunk={activeChunk}
	loading={chunkLoading}
	error={chunkError}
	onClose={closeChunk}
/>
