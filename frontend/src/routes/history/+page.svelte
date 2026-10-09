<script lang="ts">
    import { onMount } from 'svelte';
    import type { AnalysisResponse } from '$lib/types';
    import { assessmentParagraphs } from '$lib/assessmentText';
    import { linkedFollowUps } from '$lib/historyLinks';

    type RecordItem = {
        id: string; created_at: string; category: string; title: string; status: string;
        origin: string; details?: string; evidence?: string; related_id?: string;
        version?: string; duration_seconds?: number; document_count?: number;
        configuration?: Record<string, unknown>; application_id?: string;
        expected?: string; actual?: string; improvement?: string;
    };
    const categories = ['all', 'analysis', 'test', 'bug', 'note'];
    const labels: Record<string, string> = { all: 'All entries', analysis: 'Analysis runs', test: 'Test results', bug: 'Bugs & improvements', note: 'Development notes' };
    const statuses: Record<string, string[]> = { test: ['not_run', 'passed', 'failed'], bug: ['open', 'resolved'], note: ['recorded'] };
    let records: RecordItem[] = $state([]);
    let total = $state(0);
    let loading = $state(true);
    let error = $state('');
    let notice = $state('');
    let saving = $state(false);
    let filter = $state('all');
    let search = $state('');
    let showForm = $state(false);
    let category = $state('test');
    let status = $state('not_run');
    let title = $state('');
    let details = $state('');
    let evidence = $state('');
    let relatedId = $state('');
    let version = $state('');
    let expected = $state('');
    let actual = $state('');
    let improvement = $state('');
    let snapshots: Record<string, AnalysisResponse> = $state({});
    let snapshotLoading = $state('');

    function followUps(entry: RecordItem) {
        return linkedFollowUps(records, entry);
    }

    async function inspect(entry: RecordItem) {
        snapshotLoading = entry.id;
        error = '';
        try {
            const response = await fetch(`/api/history/${entry.id}`);
            if (!response.ok) throw new Error('Could not read saved result.');
            const record = await response.json();
            if (!record.result) throw new Error('No analysis snapshot is available for this entry.');
            snapshots[entry.id] = record.result;
        } catch (problem) {
            error = problem instanceof Error ? problem.message : 'Could not read saved result.';
        } finally {
            snapshotLoading = '';
        }
    }
    const visible = $derived(records.filter((entry) => (filter === 'all' || entry.category === filter) && `${entry.title} ${entry.details ?? ''} ${entry.application_id ?? ''} ${entry.id}`.toLowerCase().includes(search.toLowerCase())));

    async function load(append = false) {
        loading = true;
        error = '';
        try {
            const response = await fetch(`/api/history?limit=100&offset=${append ? records.length : 0}`);
            if (!response.ok) throw new Error('Could not load history. Check the backend connection and retry.');
            const data = await response.json();
            records = append ? [...records, ...data.items] : data.items;
            total = data.total;
        } catch (problem) {
            error = problem instanceof Error ? problem.message : 'Could not load history.';
        } finally {
            loading = false;
        }
    }

    async function save(event: SubmitEvent) {
        event.preventDefault();
        saving = true;
        error = '';
        notice = '';
        try {
            const response = await fetch('/api/history', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ category, status, title, details, evidence, related_id: relatedId, version, expected, actual, improvement })
            });
            if (!response.ok) throw new Error('Entry was not saved. Check the fields and backend connection.');
            title = ''; details = ''; evidence = ''; relatedId = ''; version = '';
            expected = ''; actual = ''; improvement = '';
            showForm = false;
            notice = 'Entry saved. Add a linked follow-up for later corrections or improvements.';
            await load();
        } catch (problem) {
            error = problem instanceof Error ? problem.message : 'Entry was not saved.';
        } finally {
            saving = false;
        }
    }

    async function download(entry: RecordItem) {
        error = '';
        try {
            const response = await fetch(`/api/history/${entry.id}`);
            if (!response.ok) throw new Error('Could not export this record.');
            const content = await response.json();
            const url = URL.createObjectURL(new Blob([JSON.stringify(content, null, 2)], { type: 'application/json' }));
            const anchor = document.createElement('a');
            anchor.href = url;
            anchor.download = `history-${entry.id}.json`;
            anchor.click();
            setTimeout(() => URL.revokeObjectURL(url), 1000);
        } catch {
            error = 'Could not export this record. Please retry.';
        }
    }

    function followUp(entry: RecordItem) {
        category = entry.category === 'analysis' ? 'note' : entry.category;
        status = statuses[category][0];
        relatedId = entry.id;
        title = `Follow-up: ${entry.title}`.slice(0, 200);
        details = ''; evidence = ''; version = '';
        expected = ''; actual = ''; improvement = '';
        showForm = true;
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    onMount(() => { void load(); });
</script>

<svelte:head><title>Development History — TraceLens</title></svelte:head>

<div class="space-y-6">
    <div class="flex flex-wrap items-start justify-between gap-4">
        <div>
            <p class="text-xs font-semibold uppercase tracking-wide text-brand-600">Internal development workspace</p>
            <h2 class="mt-2 text-2xl font-bold text-slate-900">Development History</h2>
            <p class="mt-2 max-w-2xl text-sm text-slate-500">Track runs, tests, bugs and the decisions behind each improvement. No historical results are imported.</p>
        </div>
        <div class="flex gap-2">
            <button onclick={() => load()} disabled={loading} class="neo-button rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm disabled:opacity-50">Refresh</button>
            <button onclick={() => showForm = !showForm} class="neo-button rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white">{showForm ? 'Close form' : '+ Add entry'}</button>
        </div>
    </div>

    <div class="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
        New analysis runs are saved automatically. Test results, bugs and notes are manually reported, not independently verified. A completed run is not a passed accuracy test. Use synthetic or authorised data; snapshots may contain financial information. This page is for trusted local use only.
    </div>
    {#if error}<div role="alert" class="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>{/if}
    {#if notice}<p role="status" class="text-sm text-emerald-700">{notice}</p>{/if}

    {#if showForm}
        <form onsubmit={save} class="space-y-4 neo-card rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <h3 class="font-semibold">Record evidence, not assumptions</h3>
            <div class="grid gap-4 md:grid-cols-2">
                <label class="text-sm">Expected result<textarea bind:value={expected} maxlength="6000" rows="3" class="mt-1 block w-full rounded-lg border border-slate-300 p-3"></textarea></label>
                <label class="text-sm">Actual result<textarea bind:value={actual} maxlength="6000" rows="3" class="mt-1 block w-full rounded-lg border border-slate-300 p-3"></textarea></label>
            </div>
            <label class="block text-sm">Improvement / retest plan<textarea bind:value={improvement} maxlength="6000" rows="3" class="mt-1 block w-full rounded-lg border border-slate-300 p-3"></textarea></label>
            <p class="text-sm text-slate-500">Entries are append-only in this interface. Add a linked follow-up instead of rewriting an earlier result. Never include passwords or API keys.</p>
            <div class="grid gap-4 sm:grid-cols-2">
                <label class="text-sm">Category<select bind:value={category} onchange={() => status = statuses[category][0]} class="mt-1 block w-full rounded-lg border border-slate-300 p-2"><option value="test">Test result</option><option value="bug">Bug / improvement</option><option value="note">Development note</option></select></label>
                <label class="text-sm">Status<select bind:value={status} class="mt-1 block w-full rounded-lg border border-slate-300 p-2">{#each statuses[category] as value}<option value={value}>{value.replaceAll('_', ' ')}</option>{/each}</select></label>
            </div>
            <label class="block text-sm">Title<input required maxlength="200" bind:value={title} class="mt-1 block w-full rounded-lg border border-slate-300 p-2" placeholder="What did you test or discover?" /></label>
            <label class="block text-sm">Details<textarea rows="5" maxlength="20000" bind:value={details} class="mt-1 block w-full rounded-lg border border-slate-300 p-2" placeholder="Dataset / steps → expected vs actual → cause → fix → before/after results. For notes, include your decisions and any AI assistance."></textarea></label>
            <label class="block text-sm">Evidence references<textarea rows="2" maxlength="4000" bind:value={evidence} class="mt-1 block w-full rounded-lg border border-slate-300 p-2" placeholder="Test command, report path, screenshot or commit reference. References are stored as text, not uploaded attachments."></textarea></label>
            <div class="grid gap-4 sm:grid-cols-2">
                <label class="text-sm">Related entry / run ID<input maxlength="100" bind:value={relatedId} class="mt-1 block w-full rounded-lg border border-slate-300 p-2" /></label>
                <label class="text-sm">Code version / commit (optional)<input maxlength="200" bind:value={version} class="mt-1 block w-full rounded-lg border border-slate-300 p-2" /></label>
            </div>
            <button disabled={saving || !title.trim()} class="neo-button rounded-lg bg-brand-600 px-5 py-2 text-sm font-semibold text-white disabled:opacity-50">{saving ? 'Saving…' : 'Save entry'}</button>
        </form>
    {/if}

    <div class="neo-card rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div class="flex flex-wrap gap-2" aria-label="History categories">
            {#each categories as value}
                <button aria-pressed={filter === value} onclick={() => filter = value} class="rounded-lg px-3 py-2 text-sm font-medium" class:bg-brand-600={filter === value} class:text-white={filter === value} class:bg-slate-100={filter !== value}>{labels[value]}</button>
            {/each}
        </div>
        <label class="mt-4 block text-sm text-slate-500">Search loaded entries<input bind:value={search} type="search" class="mt-1 block w-full rounded-lg border border-slate-300 p-2 text-slate-900" placeholder="Title, details or run ID" /></label>
        <p class="mt-2 text-xs text-slate-500">{records.length} of {total} entries loaded · {visible.length} matching. Counts describe records, not unresolved bugs or measured accuracy.</p>
    </div>

    {#if loading && records.length === 0}
        <p role="status" class="py-12 text-center text-slate-500">Loading history…</p>
    {:else if visible.length === 0 && !error}
        <div class="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-14 text-center">
            <h3 class="text-lg font-semibold">{total === 0 ? 'Your history starts here' : 'No matching entries'}</h3>
            <p class="mx-auto mt-2 max-w-lg text-sm text-slate-500">{total === 0 ? 'No runs, tests or bugs have been recorded yet. Start an analysis or add your first test plan. Nothing is marked as passed by default.' : 'Try another category, clear the search or load more entries.'}</p>
            <a href="/" class="mt-5 inline-block text-sm font-semibold text-brand-600">Go to analysis workspace →</a>
        </div>
    {/if}

    {#each visible as entry (entry.id)}
        <article class="neo-card rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div class="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
                <span>{labels[entry.category]} · {entry.origin === 'automatic' ? 'Automatically recorded' : 'Manually reported'}</span>
                <time datetime={entry.created_at}>{new Date(entry.created_at).toLocaleString()}</time>
            </div>
            <div class="mt-3 flex flex-wrap items-center gap-3"><h3 class="font-semibold text-slate-900">{entry.title}</h3><span class="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium">{entry.status.replaceAll('_', ' ')}</span></div>
            <p class="mt-2 line-clamp-2 break-words text-sm text-slate-600">{entry.details}</p>
            <details class="mt-4">
                <summary class="cursor-pointer text-sm font-semibold text-brand-700">View record · evidence & follow-ups</summary>
                <div class="mt-4 border-t border-slate-200 pt-4">
                <p class="whitespace-pre-wrap break-words text-sm text-slate-600">{entry.details}</p>
            {#if entry.expected || entry.actual}
                <div class="mt-4 grid gap-4 md:grid-cols-2">
                    <div class="rounded-lg bg-slate-50 p-4"><h4 class="font-semibold">Expected</h4><p class="mt-2 whitespace-pre-wrap break-words text-sm">{entry.expected || 'Not recorded'}</p></div>
                    <div class="rounded-lg bg-slate-50 p-4"><h4 class="font-semibold">Actual</h4><p class="mt-2 whitespace-pre-wrap break-words text-sm">{entry.actual || 'Not recorded'}</p></div>
                </div>
            {/if}
            {#if entry.improvement}<div class="mt-3 rounded-lg bg-brand-50 p-4"><h4 class="font-semibold">Improvement / retest plan</h4><p class="mt-2 whitespace-pre-wrap text-sm">{entry.improvement}</p></div>{/if}
            {#if followUps(entry).length > 0}
                <div class="mt-3 text-sm"><h4 class="font-semibold">Linked follow-ups (loaded records)</h4>
                    {#each followUps(entry) as linked}
                        <p class="mt-1">{linked.title} · {linked.status.replaceAll('_', ' ')}</p>
                    {/each}
                </div>
            {/if}
            {#if entry.category === 'analysis'}<p class="mt-3 text-sm text-slate-500">{entry.document_count} documents · {entry.duration_seconds}s · App version {entry.version}</p>{/if}
            {#if entry.category === 'analysis'}
                <a href={`/?saved=${entry.id}`} class="mt-3 mr-3 inline-block rounded-lg bg-brand-600 px-3 py-2 text-sm font-semibold text-white">Open full dashboard</a>
                <button class="mt-3 rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold" disabled={snapshotLoading === entry.id} onclick={() => inspect(entry)}>{snapshotLoading === entry.id ? 'Loading…' : 'Inspect saved result'}</button>
                {#if snapshots[entry.id]}
                    {@const snapshot = snapshots[entry.id]}
                    <section class="mt-4 space-y-4 rounded-lg border border-slate-300 p-4">
                        <h4 class="font-semibold">Original result — not recalculated</h4>
                        <p class="text-sm text-amber-900">This snapshot may contain known errors. Follow-up records do not overwrite it. Source IDs below are preserved as recorded.</p>
                        {#if snapshot.risk_summary}
                            <p class="text-sm font-semibold">{snapshot.risk_summary.headline}</p>
                            <details><summary class="text-sm font-semibold">Saved narrative</summary>
                                {#each assessmentParagraphs(snapshot.risk_summary.body) as paragraph}<p class="mt-3 max-w-prose whitespace-pre-wrap break-words text-sm leading-7">{paragraph}</p>{/each}
                            </details>
                        {/if}
                        <div class="overflow-x-auto">
                            <table class="w-full text-left text-sm">
                                <thead><tr><th class="p-2">Days</th><th class="p-2">Credits (RM)</th><th class="p-2">Debits (RM)</th><th class="p-2">Daily inflow (RM)</th><th class="p-2">Closing (RM)</th></tr></thead>
                                <tbody>{#each snapshot.ratios.bank_statement_metrics ?? [] as metric}<tr class="border-t border-slate-200"><td class="p-2">{metric.period_days}</td><td class="p-2">{metric.total_credits}</td><td class="p-2">{metric.total_debits}</td><td class="p-2">{metric.avg_daily_inflow}</td><td class="p-2">{metric.end_of_period_balance}</td></tr>{/each}</tbody>
                            </table>
                        </div>
                        {#each snapshot.inconsistencies as finding}<p class="text-sm">{finding.code}: {finding.message}</p>{/each}
                    </section>
                {/if}
            {/if}
            <details class="mt-4 text-sm">
                <summary class="cursor-pointer font-medium text-slate-700">Evidence & record details</summary>
                <div class="mt-3 space-y-2 break-all rounded-lg bg-slate-50 p-4 text-slate-600">
                    <p>Entry ID: {entry.id}</p>
                    {#if entry.application_id}<p>Application ID: {entry.application_id}</p>{/if}
                    {#if entry.related_id}<p>Related entry / run: {entry.related_id}</p>{/if}
                    {#if entry.version}<p>Version: {entry.version}</p>{/if}
                    {#if entry.evidence}<p class="whitespace-pre-wrap">Evidence references: {entry.evidence}</p>{:else if entry.origin === 'manual'}<p>No evidence reference supplied. This is a self-reported entry.</p>{/if}
                    {#if entry.configuration}<pre class="overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(entry.configuration, null, 2)}</pre>{/if}
                    {#if entry.category === 'analysis'}<p>The JSON export includes the saved analysis result. It is a snapshot, not a verified assessment or a complete archive of source PDFs.</p>{/if}
                </div>
            </details>
            <div class="mt-4 flex gap-4"><button onclick={() => followUp(entry)} class="text-sm font-semibold text-brand-600">Add follow-up</button><button onclick={() => download(entry)} class="text-sm font-semibold text-slate-600">Export JSON</button></div>
                </div>
            </details>
        </article>
    {/each}
    {#if records.length < total}<button onclick={() => load(true)} disabled={loading} class="neo-button rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm">{loading ? 'Loading…' : 'Load more'}</button>{/if}
</div>
