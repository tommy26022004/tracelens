<script lang="ts">
    import { bankReconciliation } from '$lib/bankReconciliation';
    import { createDemoPackage } from '$lib/demoPackage';
    import { apiUrl } from '$lib/http';
    import { onMount } from 'svelte';
    let savedResult = $state(false);
    let loadingSaved = $state(false);
    let tourOpen = $state(false);
    let tourStep = $state(0);
    let demoLoading = $state(false);
    onMount(() => {
        const id = new URL(window.location.href).searchParams.get('saved');
        if (!id && window.localStorage.getItem('tracelens-tour-seen-v1') !== 'true') {
            tourOpen = true;
        }
        if (!id) return;
        loadingSaved = true;
        void fetch(apiUrl(`/api/history/${encodeURIComponent(id)}`)).then(async (response) => {
            if (!response.ok) throw new Error('Saved analysis could not be loaded.');
            const record = await response.json();
            if (record.category !== 'analysis' || !record.result) throw new Error('No saved analysis result is available.');
            result = record.result;
            savedResult = true;
        }).catch((error) => analyseError = String(error)).finally(() => loadingSaved = false);
    });
    import { assessmentParagraphs, assessmentHeading, assessmentGroupHeading, humanChecksForDisplay, retrievalLabel } from '$lib/assessmentText';
	import { analyseApplication, fetchChunk } from '$lib/api';
    import CitedText from '$lib/components/CitedText.svelte';
    import CitationButton from '$lib/components/CitationButton.svelte';
    import { citationLabel, citationTitle } from '$lib/citations';
	import ChunkModal from '$lib/components/ChunkModal.svelte';
	import RetrievalPanel from '$lib/components/RetrievalPanel.svelte';
	import type { AnalysisResponse, ChunkDetail, Rating } from '$lib/types';

	let files: File[] = $state([]);
	let dragging = $state(false);
	let analysing = $state(false);
    let result: AnalysisResponse | null = $state(null);
    const references = $derived.by(() => result?.citation_sources ?? {});
	let analyseError: string | null = $state(null);
	let jobProgress = $state(0);
	let jobPhase = $state('');
	const phaseLabels: Record<string, string> = { uploading: 'Uploading documents', queued: 'Preparing analysis', reading: 'Reading documents', extracting: 'Extracting information', validating: 'Checking documents', calculating: 'Calculating metrics', assessing: 'Assessing the 5Cs', summarising: 'Preparing assessment', saving: 'Saving results', completed: 'Analysis complete', failed: 'Analysis stopped' };
	let activeView = $state('overview');
	let sourceSearch = $state('');
	const views = [
		{ id: 'overview', label: 'Overview', description: 'Start with the assessment, then review the evidence behind it.' },
		{ id: 'evidence', label: 'Documents & Evidence', description: 'Inspect source documents and the excerpts supplied to the AI.' },
		{ id: 'technical', label: 'Technical Details', description: 'Inspect calculated metrics, processing steps and diagnostic messages.' }
	];
	const dimensionDescriptions = {
		character: 'Business conduct and repayment behaviour',
		capacity: 'Ability to meet repayment obligations',
		capital: 'Financial position and capital structure',
		collateral: 'Assets or security supporting the application',
		conditions: 'Business context and external risks'
	};
	const visibleSources = $derived(Object.keys(references).filter((chunkId) =>
		citationTitle(chunkId, references).toLowerCase().includes(sourceSearch.toLowerCase())
	));

	let activeChunkId: string | null = $state(null);
	let activeChunk: ChunkDetail | null = $state(null);
	let chunkLoading = $state(false);
	let chunkError: string | null = $state(null);

	const dimensionOrder = ['character', 'capacity', 'capital', 'collateral', 'conditions'] as const;
	const tourSteps = [
		{ title: 'Start with a complete package', body: 'Upload your own PDFs or load the four-file synthetic demo. TraceLens accepts bank, SSM, financial and tax documents.' },
		{ title: 'Run the six-stage analysis', body: 'The workflow reads, extracts, validates, calculates ratios, assesses the 5Cs and prepares a source-traced summary.' },
		{ title: 'Inspect every important claim', body: 'Open citations to compare extracted values with the original PDF page and retrieved context.' },
		{ title: 'Keep a human in control', body: 'Ratings are provisional decision support. Review missing evidence, warnings and recommended checks before relying on a result.' }
	];

	function openTour() {
		tourStep = 0;
		tourOpen = true;
	}

	function closeTour() {
		window.localStorage.setItem('tracelens-tour-seen-v1', 'true');
		tourOpen = false;
	}

	async function loadDemoPackage() {
		demoLoading = true;
		analyseError = null;
		await new Promise((resolve) => setTimeout(resolve, 180));
		files = createDemoPackage();
		demoLoading = false;
		window.localStorage.setItem('tracelens-tour-seen-v1', 'true');
		requestAnimationFrame(() => document.querySelector('[data-upload-card]')?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
	}

	function addFiles(selected: File[]) {
		const pdfs = selected.filter((file) => file.name.toLowerCase().endsWith('.pdf'));
		const merged = new Map(
			files.map((file) => [`${file.name}:${file.size}:${file.lastModified}`, file])
		);
		for (const file of pdfs) {
			merged.set(`${file.name}:${file.size}:${file.lastModified}`, file);
		}
		files = Array.from(merged.values());
	}

	function onFileChange(event: Event) {
		const input = event.target as HTMLInputElement;
		if (input.files) addFiles(Array.from(input.files));
		input.value = '';
	}

	function onDrop(event: DragEvent) {
		event.preventDefault();
		dragging = false;
		const dropped = event.dataTransfer?.files;
		if (dropped) {
			addFiles(Array.from(dropped));
		}
	}

	function removeFile(fileToRemove: File) {
		files = files.filter((file) => file !== fileToRemove);
	}

	function resetAnalysis() {
        savedResult = false;
        window.history.replaceState({}, '', '/');
		activeView = 'overview';
		sourceSearch = '';
		closeChunk();
		files = [];
		result = null;
		analyseError = null;
		jobProgress = 0;
		jobPhase = '';
	}

	function formatMoney(value: string): string {
		return new Intl.NumberFormat('en-MY', {
			style: 'currency',
			currency: 'MYR',
			minimumFractionDigits: 2
		}).format(Number(value));
	}

	function shortDocumentName(documentId: string): string {
		return (documentId.split('/').at(-1) ?? documentId)
			.replace(/^\d+_/, '')
			.replaceAll('__', ' / ')
			.replaceAll('_', ' ');
	}

	async function submit() {
		if (files.length === 0) return;
		activeView = 'overview';
		analysing = true;
		analyseError = null;
		result = null;
		jobProgress = 0;
		jobPhase = 'uploading';
		try {
			const completedResult = await analyseApplication(files, (update) => {
				jobProgress = update.progress;
				jobPhase = update.phase;
			});
			jobProgress = 100;
			jobPhase = 'completed';
			await new Promise((resolve) => setTimeout(resolve, 650));
			result = completedResult;
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
            const fetched = await fetchChunk(chunkId, result?.application_id);
            if (activeChunkId === chunkId) activeChunk = fetched;
		} catch (err) {
            if (activeChunkId === chunkId) chunkError = err instanceof Error ? err.message : String(err);
		} finally {
            if (activeChunkId === chunkId) chunkLoading = false;
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
    {#if tourOpen}
        <div class="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/55 p-4" role="presentation" onclick={(event) => { if (event.target === event.currentTarget) closeTour(); }}>
            <div role="dialog" aria-modal="true" aria-labelledby="tour-title" class="w-full max-w-xl rounded-3xl border border-white/70 bg-[#f4f6ec] p-6 shadow-2xl sm:p-8">
                <div class="flex items-start justify-between gap-4">
                    <div>
                        <p class="text-xs font-semibold uppercase tracking-[0.18em] text-brand-700">60-second product tour</p>
                        <h2 id="tour-title" class="mt-2 text-2xl font-bold text-slate-950">{tourSteps[tourStep].title}</h2>
                    </div>
                    <button type="button" aria-label="Close product tour" class="rounded-full border border-slate-300 bg-white px-3 py-1.5 text-sm font-semibold text-slate-600" onclick={closeTour}>Close</button>
                </div>
                <p class="mt-5 text-base leading-7 text-slate-600">{tourSteps[tourStep].body}</p>
                <div class="mt-7 grid grid-cols-4 gap-2" aria-label={`Tour step ${tourStep + 1} of ${tourSteps.length}`}>
                    {#each tourSteps as _, index}
                        <div class="h-2 rounded-full {index <= tourStep ? 'bg-brand-600' : 'bg-slate-200'}"></div>
                    {/each}
                </div>
                <div class="mt-6 flex flex-wrap items-center justify-between gap-3">
                    <p class="text-sm text-slate-500">Step {tourStep + 1} of {tourSteps.length}</p>
                    <div class="flex gap-2">
                        {#if tourStep > 0}<button type="button" class="rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-semibold" onclick={() => tourStep -= 1}>Back</button>{/if}
                        {#if tourStep < tourSteps.length - 1}
                            <button type="button" class="rounded-xl bg-brand-600 px-5 py-2 text-sm font-semibold text-white" onclick={() => tourStep += 1}>Next</button>
                        {:else}
                            <button type="button" class="rounded-xl bg-brand-600 px-5 py-2 text-sm font-semibold text-white" onclick={closeTour}>Start exploring</button>
                        {/if}
                    </div>
                </div>
            </div>
        </div>
    {/if}
    {#if loadingSaved}<p role="status" class="p-5">Loading saved analysis — no AI call…</p>{/if}
    {#if savedResult}<div class="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">Saved result — not recalculated. This is the original analysis and may contain previously identified errors. <a href="/cases" class="ml-2 font-semibold underline">Back to company cases</a></div>{/if}
	{#if !result && !loadingSaved}
	<div class="neo-card overflow-hidden rounded-3xl border border-brand-200 bg-gradient-to-br from-white via-brand-50/70 to-amber-50 p-6 shadow-sm sm:p-8">
		<div class="grid gap-8 lg:grid-cols-[1.25fr_1fr] lg:items-center">
			<div>
				<p class="text-xs font-semibold uppercase tracking-[0.18em] text-brand-700">New to TraceLens?</p>
				<h2 class="mt-3 max-w-2xl text-3xl font-bold tracking-tight text-slate-950 sm:text-4xl">Turn an SME loan package into a reviewable, source-linked assessment.</h2>
				<p class="mt-4 max-w-2xl text-base leading-7 text-slate-600">Try a safe synthetic company package in one click, or bring your own authorised PDFs. No lending decision is made automatically.</p>
				<div class="mt-6 flex flex-wrap gap-3">
					<button type="button" class="neo-button rounded-xl bg-brand-600 px-5 py-3 text-sm font-semibold text-white disabled:opacity-60" disabled={demoLoading} onclick={loadDemoPackage}>{demoLoading ? 'Preparing demo…' : 'Try sample package'}</button>
					<button type="button" class="neo-button rounded-xl border border-slate-300 bg-white px-5 py-3 text-sm font-semibold text-slate-700" onclick={openTour}>Take the 60-second tour</button>
				</div>
				<p class="mt-3 text-xs text-slate-500">Includes four generated PDFs for a fictitious Malaysian SME. Synthetic test data only.</p>
			</div>
			<ol class="grid gap-3 text-sm text-slate-700">
				<li class="rounded-2xl border border-white/80 bg-white/65 p-4"><span class="mr-3 font-bold text-brand-700">01</span>Load bank, SSM, financial and tax PDFs</li>
				<li class="rounded-2xl border border-white/80 bg-white/65 p-4"><span class="mr-3 font-bold text-brand-700">02</span>Run extraction, validation, ratios and 5C assessment</li>
				<li class="rounded-2xl border border-white/80 bg-white/65 p-4"><span class="mr-3 font-bold text-brand-700">03</span>Review citations, limitations and human checks</li>
			</ol>
		</div>
	</div>
	<!-- Upload card -->
	<div data-upload-card class="upload-surface neo-card scroll-mt-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
		<h2 class="text-base font-semibold text-slate-900">Upload SME application package</h2>
		<p class="mt-1 text-sm text-slate-500">
			Drag in or pick the bank statements, SSM registration, and other supporting PDFs. The agent
			will run all six steps and return a source-traced summary.
		</p>
		<p class="mt-2 text-xs text-slate-400">Supports up to 50 PDFs and 100 MB per package.</p>

		<div
			class="neo-inset mt-4 flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-300 p-8 text-center transition-colors"
			class:bg-brand-50={dragging}
			class:border-brand-400={dragging}
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
			<p class="mt-2 text-sm text-slate-600">Drop PDFs here, or add them one at a time</p>
			<label class="mt-2 cursor-pointer text-sm font-semibold text-brand-700 hover:text-brand-600">
				<input
					type="file"
					accept="application/pdf"
					multiple
					class="sr-only"
					onchange={onFileChange}
				/>
				browse to select
			</label>
		</div>

		{#if files.length > 0}
			<p class="mt-4 text-sm font-medium text-slate-700">
				{files.length} PDFs · {(files.reduce((total, file) => total + file.size, 0) / 1048576).toFixed(1)} MB
			</p>
			<ul class="mt-2 max-h-64 space-y-1 overflow-y-auto text-sm text-slate-700">
				{#each files as file (file)}
					<li class="flex items-center gap-2">
						<span class="text-slate-400">·</span>
						<span class="font-medium">{file.name}</span>
						<span class="text-xs text-slate-400">{(file.size / 1024).toFixed(1)} KB</span>
						<button
							type="button"
							class="ml-auto shrink-0 rounded-lg bg-red-700 px-3 py-2 text-xs font-semibold text-white shadow-sm hover:bg-red-800"
							onclick={() => removeFile(file)}
							aria-label={`Remove ${file.name}`}
						>
							Remove
						</button>
					</li>
				{/each}
			</ul>
		{/if}

		<button
			type="button"
			class="neo-button mt-4 inline-flex items-center rounded-xl bg-brand-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-brand-700 disabled:cursor-not-allowed disabled:bg-slate-300"
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
		{#if analysing}
			<div class="mt-3">
				<div class="flex justify-between text-xs text-slate-500">
					<span>{phaseLabels[jobPhase] ?? 'Processing documents'}</span><span>{jobProgress}%</span>
				</div>
				<div class="mt-1 h-2 overflow-hidden rounded-full bg-slate-100">
					<div role="progressbar" aria-label="Analysis progress" aria-valuemin={0} aria-valuemax={100} aria-valuenow={jobProgress} class="h-full bg-brand-600 transition-[width] duration-500 ease-out motion-reduce:transition-none" style={`width: ${jobProgress}%`}></div>
				</div>
			</div>
		{/if}

		{#if analyseError}
			<p class="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
				{analyseError}
			</p>
		{/if}
	</div>
	{/if}

	{#if result}
		{@const failedDocuments = 'failed_documents' in result.package_inventory ? result.package_inventory.failed_documents : 0}
		{@const ocrEntries = Object.entries(result.needs_ocr_pages ?? {})}
		{@const parseErrors = result.errors.filter((error) => error.node === 'parse')}
		<div class="flex flex-col justify-between gap-4 border-b border-slate-200 pb-5 sm:flex-row sm:items-end">
			<div>
				<div class="flex items-center gap-2">
					<span class="h-2.5 w-2.5 rounded-full {failedDocuments > 0 ? 'bg-amber-500' : 'bg-emerald-500'}"></span>
					<p class="text-xs font-semibold tracking-wide uppercase {failedDocuments > 0 ? 'text-amber-800' : 'text-emerald-700'}">{failedDocuments > 0 ? 'Processing completed with document failures · human review required' : 'Analysis run finished · human review required'}</p>
				</div>
				<h2 class="mt-2 text-2xl font-bold tracking-tight text-slate-950">Credit assessment dashboard</h2>
				<p class="mt-1 text-xs text-slate-500">Application ID: {result.application_id}</p>
                <a href="/cases" class="mt-2 inline-block text-sm font-semibold text-brand-700 underline">Manage company case / link this saved run →</a>
			</div>
			<button
				type="button"
				class="neo-button rounded-lg bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm ring-1 ring-slate-200 hover:bg-slate-50"
				onclick={resetAnalysis}
			>
				Analyse another package
			</button>
		</div>
		<div class="grid gap-6 sm:grid-cols-3">
			<div class="neo-card neo-stat rounded-xl border border-slate-200 bg-white p-4">
				<p class="neo-label text-xs font-semibold uppercase tracking-wide text-slate-500">Document processing</p>
				<p class="neo-stat-value mt-2 font-semibold text-slate-900">{result.package_inventory?.extracted_documents ?? '—'} / {result.package_inventory?.total_documents ?? result.document_ids.length} processed</p>
				<p class="mt-1 text-sm text-slate-500">{result.package_inventory?.total_pages ?? '—'} pages · {result.package_inventory?.failed_documents ?? '—'} failed</p>
			</div>
			<div class="neo-card neo-stat rounded-xl border border-slate-200 bg-white p-4">
				<p class="neo-label text-xs font-semibold uppercase tracking-wide text-slate-500">Evidence retrieval</p>
				<p class="mt-3 text-xl font-semibold text-slate-900">{retrievalLabel(result.retrieval?.status)}</p>
				<p class="mt-2 text-xs text-slate-600">Search status only — not evidence sufficiency across the 5Cs.</p>
				<button type="button" class="mt-1 text-sm font-medium text-brand-700 hover:underline" onclick={() => activeView = 'evidence'}>{result.retrieval?.evidence.length ?? 0} excerpts · Inspect evidence →</button>
			</div>
			<div class="neo-card neo-stat neo-stat-warning rounded-xl border border-amber-200 bg-amber-50 p-4">
				<p class="neo-label text-xs font-semibold uppercase tracking-wide text-amber-800">Decision support only</p>
				<p class="neo-stat-value mt-2 font-semibold text-slate-900">Human verification required</p>
				<p class="mt-1 text-sm text-slate-600">Processing completion does not verify the conclusions.</p>
			</div>
		</div>
		{#if ocrEntries.length > 0}
			<div class="rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950" role="alert">
				<p class="font-semibold">Image-only PDF detected — OCR is required but is not currently supported.</p>
				<ul class="mt-2 list-disc pl-5">
					{#each ocrEntries as [documentId, pages] (documentId)}
						<li>{shortDocumentName(documentId)} · page{pages.length === 1 ? '' : 's'} {pages.join(', ')}</li>
					{/each}
				</ul>
			</div>
		{/if}
		{#if parseErrors.length > 0}
			<div class="rounded-xl border border-red-300 bg-red-50 p-4 text-sm text-red-900 shadow-sm" role="alert">
				<p class="font-semibold">Invalid or damaged PDF detected — no evidence was extracted from the affected file.</p>
				<ul class="mt-1 list-disc space-y-1 pl-5">
					{#each parseErrors as error (error.message)}
						<li>{error.message}</li>
					{/each}
				</ul>
			</div>
		{/if}
		<nav aria-label="Assessment sections" class="neo-tabs flex flex-wrap gap-2 rounded-xl border border-slate-200 bg-white p-2">
			{#each views as view}
				<button type="button" aria-pressed={activeView === view.id} class="rounded-lg px-4 py-3 text-sm font-semibold transition-colors {activeView === view.id ? 'bg-brand-600 text-white' : 'text-slate-600 hover:bg-slate-100'}" onclick={() => activeView = view.id}>{view.label}</button>
			{/each}
		</nav>
		<p class="text-sm text-slate-500">{views.find((view) => view.id === activeView)?.description}</p>
		{#if activeView === 'evidence' && result.package_inventory && 'total_documents' in result.package_inventory}
			{@const inventory = result.package_inventory}
			<div class="neo-card rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
				<div class="flex items-center justify-between">
					<h2 class="text-base font-semibold text-slate-900">Package inventory</h2>
					<span class="rounded-full px-2 py-1 text-xs font-medium {inventory.complete ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}">
						{inventory.complete ? 'Complete' : 'Review required'}
					</span>
				</div>
				<div class="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
					<div><p class="text-xs text-slate-500">Documents</p><p class="text-xl font-semibold">{inventory.total_documents}</p></div>
					<div><p class="text-xs text-slate-500">Pages</p><p class="text-xl font-semibold">{inventory.total_pages}</p></div>
					<div><p class="text-xs text-slate-500">Processed</p><p class="text-xl font-semibold">{inventory.extracted_documents}</p></div>
					<div><p class="text-xs text-slate-500">Failed</p><p class="text-xl font-semibold">{inventory.failed_documents}</p></div>
				</div>
				<div class="mt-4 flex flex-wrap gap-2">
					{#each Object.entries(inventory.documents_by_kind) as [kind, count] (kind)}
						<span class="rounded bg-slate-100 px-2 py-1 text-xs text-slate-700">{kind.replaceAll('_', ' ')}: {count}</span>
					{/each}
				</div>
				{#if inventory.missing_bank_months.length || inventory.missing_core_kinds.length || inventory.duplicate_document_ids.length}
					<p class="mt-4 text-sm text-amber-700">
						Bank coverage: {!(result.ratios?.bank_statement_metrics?.length) ? 'Not assessed — no usable bank statements' : inventory.missing_bank_months.length ? `Missing months: ${inventory.missing_bank_months.join(', ')}` : 'No gaps detected within the configured period'} · Missing types: {inventory.missing_core_kinds.join(', ') || 'none'} · Duplicates: {inventory.duplicate_document_ids.length}
					</p>
				{/if}
			</div>
		{/if}
		{#if activeView === 'overview'}
		{#if result.risk_summary}
            {@const narrativeParagraphs = assessmentParagraphs(result.risk_summary.body)}
			{@const humanChecks = humanChecksForDisplay(result.risk_summary.recommended_human_checks, result.inconsistencies.map((finding) => finding.code))}
			<div class="neo-card rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
				<h2 class="text-base font-semibold text-slate-900">Assessment at a glance</h2>
				<p class="mt-1 text-xs text-slate-500">
                    AI-generated assessment, not a verified lending decision. Select a source to inspect its original page.
				</p>

				<p class="mt-4 text-lg leading-snug font-medium text-slate-900">
                    <CitedText text={result.risk_summary.headline} {references} onCitationClick={openChunk} />
				</p>
				<details class="mt-4 border-t border-slate-100 pt-4">
					<summary class="cursor-pointer text-sm font-semibold text-brand-700 hover:text-brand-600">
						Read full assessment and supporting sources
					</summary>
                    <div class="mt-5 grid items-start gap-4 text-sm leading-7 text-slate-700 lg:grid-cols-2">
                        {#each narrativeParagraphs as paragraph, index}
                            {@const groupHeading = assessmentGroupHeading(paragraph)}
                            {#if groupHeading}
                                <h3 class="border-b border-brand-200 pb-2 pt-3 font-semibold text-brand-700 lg:col-span-2">{groupHeading}</h3>
                            {:else}
                            <section class="rounded-2xl border border-white/80 bg-white/40 p-5">
                                <h3 class="mb-3 flex items-center gap-3 text-xs font-semibold uppercase tracking-wide text-brand-700"><span class="flex h-7 w-7 items-center justify-center rounded-full bg-brand-100">{String(narrativeParagraphs.slice(0, index + 1).filter((item) => !assessmentGroupHeading(item)).length).padStart(2, '0')}</span>{assessmentHeading(paragraph)}</h3>
                                <p class="whitespace-pre-line break-words"><CitedText text={paragraph} {references} onCitationClick={openChunk} /></p>
                            </section>
                            {/if}
                        {/each}
					</div>
				</details>

				{#if humanChecks.length > 0}
					<div class="mt-4 border-t border-slate-100 pt-4">
						<h3 class="neo-label text-xs font-medium tracking-wide text-slate-500 uppercase">
							Recommended human checks
						</h3>
						<ul class="mt-3 grid gap-3 text-sm leading-6 text-slate-700 md:grid-cols-2">
							{#each humanChecks as check, index (check)}
								<li class="neo-check flex gap-3 rounded-lg bg-amber-50 p-3"><span class="font-semibold text-amber-800">{index + 1}.</span><span class="min-w-0 break-words"><CitedText text={check} {references} onCitationClick={openChunk} /></span></li>
							{/each}
						</ul>
					</div>
				{/if}
			</div>
		{/if}

		<!-- 5C grid -->
		{#if result.five_c && 'character' in result.five_c}
			<div class="neo-card rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
				<h2 class="text-base font-semibold text-slate-900">5C credit assessment</h2>
				<p class="mt-1 text-sm text-slate-500">Provisional ratings. Expand a dimension to read the full rationale and inspect its sources.</p>
				<div class="mt-6 grid items-start gap-5 md:grid-cols-2 xl:grid-cols-3">
					{#each dimensionOrder as key (key)}
						{@const dim = result.five_c[key]}
						<details class="neo-dimension group rounded-lg border border-slate-200 p-4">
							<summary class="cursor-pointer">
							<span class="ml-1 font-semibold capitalize text-slate-900">{dim.name}</span>
							<span
								class="mt-1 inline-block rounded-full px-2 py-0.5 text-xs font-medium {ratingClass(
									dim.rating
								)}"
							>
								{dim.rating.replace('_', ' ')}
							</span>
							<span class="mt-2 block text-sm text-slate-500">{dimensionDescriptions[key]}</span>
							<span class="mt-2 line-clamp-2 text-sm leading-6 text-slate-700 group-open:hidden">{dim.reasoning}</span>
							</summary>
							<p class="mt-4 text-sm leading-7 text-slate-700">{dim.reasoning}</p>
							{#if dim.flags_for_human_review?.length}
								<ul class="mt-3 space-y-2 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
									{#each dim.flags_for_human_review as flag}<li>{flag}</li>{/each}
								</ul>
							{/if}
							{#if dim.evidence_chunk_ids.length > 0}
								<div class="mt-2 flex flex-wrap gap-1">
                                    {#each [...new Set(dim.evidence_chunk_ids)] as cid (cid)}
                                        <CitationButton chunkId={cid} {references} onCitationClick={openChunk} />
									{/each}
								</div>
							{/if}
						</details>
					{/each}
				</div>
			</div>
		{/if}

		<!-- Inconsistencies -->
		{#if result.inconsistencies.length > 0}
			<div class="neo-card rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
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
                                    {#each [...new Set(issue.citations)] as cid (cid)}
                                        <CitationButton chunkId={cid} {references} onCitationClick={openChunk} />
									{/each}
								</div>
							{/if}
						</li>
					{/each}
				</ul>
			</div>
		{/if}

        {/if}
		{#if activeView === 'evidence'}
        {#if Object.keys(references).length > 0}
            <details open class="neo-card rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
                <summary class="cursor-pointer text-sm font-semibold text-slate-900">
                    Sources cited or retrieved ({Object.keys(references).length})
                </summary>
				<label class="mt-4 block text-sm font-medium text-slate-600">Find a source
					<input type="search" bind:value={sourceSearch} placeholder="Search filename or page…" class="mt-2 block w-full rounded-lg border border-slate-300 px-3 py-2 font-normal" />
				</label>
                <ul class="mt-3 max-h-96 space-y-2 overflow-auto text-sm">
                    {#each visibleSources as chunkId (chunkId)}
                        <li>
                            <button type="button" class="text-left text-slate-700 hover:underline" onclick={() => openChunk(chunkId)}>
                                {citationLabel(chunkId, references)} {citationTitle(chunkId, references)}
                            </button>
                        </li>
                    {/each}
                    {#if visibleSources.length === 0}<li class="p-3 text-slate-500">No matching sources.</li>{/if}
                </ul>
            </details>
        {/if}

		{#if result.retrieval?.application_id}
			<RetrievalPanel retrieval={result.retrieval} {references} onCitationClick={openChunk} />
		{:else}
			<p class="neo-card rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-600">Retrieval details are unavailable for this result.</p>
		{/if}
		{/if}

		{#if activeView === 'technical'}
        {#each result.tax_returns ?? [] as tax}
            <section class="neo-card space-y-4 rounded-2xl p-6">
                <h2 class="font-semibold">Tax return · Year of assessment {tax.year_of_assessment}</h2>
                <p>{tax.company_name} · {tax.tax_reference_number}</p>
                <p class="text-sm text-slate-600">Document-reported figures, not independently verified. Tax payable does not establish payment, audited profit or repayment capacity.</p>
                <dl class="grid gap-4 sm:grid-cols-3">
                    <div><dt>Gross business income</dt><dd>RM {Number(tax.gross_business_income).toLocaleString('en-MY', {minimumFractionDigits: 2})}</dd></div>
                    <div><dt>Chargeable income</dt><dd>RM {Number(tax.chargeable_income).toLocaleString('en-MY', {minimumFractionDigits: 2})}</dd></div>
                    <div><dt>Tax payable</dt><dd>RM {Number(tax.tax_payable).toLocaleString('en-MY', {minimumFractionDigits: 2})}</dd></div>
                </dl>
                <button class="font-semibold underline" onclick={() => openChunk(tax.chunk_id)}>Inspect tax source</button>
            </section>
        {/each}
        {#each result.ratios.financial_ratios ?? [] as financial}
            <section class="neo-card space-y-4 rounded-2xl p-6">
                <h2 class="font-semibold">Financial ratios · FY {financial.period_end}</h2>
                <p class="text-sm text-slate-600">Calculated from reported financial figures. Interpretation bands are prototype rules, not lending decisions. Historical results are not recalculated.</p>
				{#if Number(financial.unit_multiplier ?? '1') !== 1}
					<p class="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">Source amounts were reported in {financial.source_display_unit}; values below were normalized ×{Number(financial.unit_multiplier).toLocaleString('en-MY')} to {financial.canonical_unit ?? 'RM'} before calculations.</p>
				{/if}
                <div class="overflow-x-auto"><table class="w-full text-left text-sm">
                    <thead class="bg-slate-100"><tr><th class="p-3">Ratio</th><th class="p-3">Value</th><th class="p-3">Formula / limitation</th></tr></thead>
                    <tbody>{#each ['current_ratio', 'debt_to_equity', 'net_profit_margin', 'interest_coverage', 'dsr'] as key}
                        {@const ratio = financial[key as 'current_ratio']}
                        <tr class="border-t border-slate-200 align-top"><td class="p-3 font-medium">{ratio.name}</td><td class="whitespace-nowrap p-3">{ratio.value === null ? 'Not available' : key === 'net_profit_margin' ? `${(Number(ratio.value) * 100).toFixed(2)}%` : `${Number(ratio.value).toFixed(4)}×`}</td><td class="p-3"><p>{ratio.formula}</p><p class="mt-1 text-xs text-slate-500">{ratio.explanation}</p>{#if key === 'dsr' && ratio.value !== null}<p class="mt-2 text-amber-800">Historical estimate — not verified debt service. Do not use as a confirmed repayment-capacity measure.</p>{/if}</td></tr>
                    {/each}</tbody>
                </table></div>
                <details><summary class="cursor-pointer text-sm font-semibold">Reported calculation inputs (RM)</summary><div class="mt-3 grid gap-3 sm:grid-cols-3">{#each Object.entries(financial.inputs ?? {}) as [name, value]}<div class="rounded-lg border border-slate-200 p-3"><p class="text-xs text-slate-500">{name.replaceAll('_', ' ')}</p><p>{formatMoney(value)}</p></div>{/each}</div>{#if !financial.inputs}<p class="mt-2 text-sm">Input breakdown was not saved in this older result. Inspect its original source.</p>{/if}</details>
            </section>
        {/each}
        {#if result.ratios.financial_trend && Object.keys(result.ratios.financial_trend.revenue_by_year ?? {}).length}
            <section class="neo-card rounded-2xl p-6"><h2 class="font-semibold">Reported financial trend</h2><div class="mt-4 overflow-x-auto"><table class="w-full text-left text-sm"><thead><tr><th class="p-3">Year</th><th class="p-3">Revenue (RM)</th><th class="p-3">Net profit (RM)</th></tr></thead><tbody>{#each Object.entries(result.ratios.financial_trend.revenue_by_year as Record<string, string>) as [year, revenue]}<tr class="border-t border-slate-200"><td class="p-3">{year}</td><td class="p-3">{formatMoney(revenue)}</td><td class="p-3">{formatMoney((result.ratios.financial_trend.net_profit_by_year as Record<string, string>)[year])}</td></tr>{/each}</tbody></table></div></section>
        {/if}
		<details open class="group neo-card rounded-xl border border-slate-200 bg-white shadow-sm">
			<summary class="flex cursor-pointer list-none items-center justify-between px-6 py-5">
				<div>
					<p class="text-xs font-medium tracking-wide text-slate-500 uppercase">Audit trail</p>
					<h2 class="mt-1 text-base font-semibold text-slate-900">Technical metrics and reasoning</h2>
				</div>
				<span class="text-sm font-semibold text-brand-700 group-open:hidden">Expand</span>
				<span class="hidden text-sm font-semibold text-brand-700 group-open:inline">Collapse</span>
			</summary>
		<div class="grid gap-6 border-t border-slate-100 p-6 {result.ratios?.bank_statement_metrics?.length ? 'md:grid-cols-2' : 'grid-cols-1'}">
			{#if result.ratios?.bank_statement_metrics?.length}
				<div class="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
					<div class="flex items-center justify-between border-b border-slate-200 bg-zinc-50 px-4 py-3">
						<h2 class="text-sm font-semibold text-slate-900">Bank-statement metrics</h2>
						<span class="text-xs text-slate-500">{result.ratios.bank_statement_metrics.length} statements</span>
					</div>
					<div class="max-h-[34rem] overflow-auto">
						<table class="min-w-full divide-y divide-slate-200 text-left text-xs">
							<thead class="bg-slate-100 text-xs tracking-wide text-slate-800">
								<tr>
									<th class="px-4 py-3 font-semibold">Statement</th>
									<th scope="col" class="px-4 py-3 font-semibold">Balance change / inflows less outflows (RM)</th>
									<th scope="col" class="px-4 py-3 font-semibold">Daily inflow (RM/day)</th>
									<th scope="col" class="px-4 py-3 font-semibold">Closing balance (RM)</th>
								</tr>
							</thead>
							<tbody class="divide-y divide-slate-100 bg-white">
								{#each result.ratios.bank_statement_metrics as metric (metric.document_id)}
                                    {@const reconciliation = bankReconciliation(metric)}
									<tr class="hover:bg-brand-50/40">
										<td class="max-w-56 px-4 py-3 font-medium text-slate-700">{shortDocumentName(metric.document_id)}</td>
                                        <td class="min-w-64 px-4 py-3 text-slate-800">
                                            <p>Closing − opening: {formatMoney(metric.net_change)}</p>
                                            <p>Reported credits − debits: {reconciliation.movement === null ? 'Unavailable' : formatMoney(reconciliation.movement)}</p>
                                            {#if reconciliation.mismatch}
                                                <p class="mt-2 rounded-lg bg-amber-50 p-2 font-semibold text-amber-900">Reconciliation required · Difference: {reconciliation.difference === null ? 'Unavailable' : formatMoney(reconciliation.difference)}. Do not treat either value as verified cash flow.</p>
                                            {:else}
                                                <p class="mt-1 text-xs text-slate-500">Arithmetic agrees; source figures are not independently verified.</p>
                                            {/if}
                                        </td>
										<td class="whitespace-nowrap px-4 py-3 text-slate-600">{formatMoney(metric.avg_daily_inflow)}</td>
										<td class="whitespace-nowrap px-4 py-3 text-slate-900">{formatMoney(metric.end_of_period_balance)}</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				</div>
			{/if}

			<div class="neo-card rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
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
		</details>
		{/if}
	{/if}
</section>

<ChunkModal
	chunkId={activeChunkId}
	chunk={activeChunk}
	loading={chunkLoading}
	error={chunkError}
	onClose={closeChunk}
/>
