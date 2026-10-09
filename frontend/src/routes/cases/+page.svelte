<script lang="ts">
    import { onMount } from 'svelte';
    type CaseRecord = { id: string; company: string; reference: string; environment: string; status: string; updated_at: string; runs: { id: string; application_id: string; created_at: string; document_count: number }[]; events: { at: string; status: string; note: string; run_id: string | null }[] };
    type Run = { id: string; title: string; application_id: string; created_at: string; category: string; status: string };
    let cases: CaseRecord[] = $state([]);
    let runs: Run[] = $state([]);
    let company = $state('');
    let reference = $state('');
    let environment = $state('test');
    let selected = $state('');
    let status = $state('under_review');
    let note = $state('');
    let runId = $state('');
    let search = $state('');
    let error = $state('');
    let busy = $state(false);
    const labels: Record<string, string> = { under_review: 'Under review', awaiting_documents: 'Awaiting documents', reviewed: 'Reviewed' };
    const active = $derived(cases.find((item) => item.id === selected));
    const visible = $derived(cases.filter((item) => `${item.company} ${item.reference}`.toLowerCase().includes(search.toLowerCase())));

    async function request(path: string, payload?: unknown) {
        const response = await fetch(path, payload ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) } : {});
        if (!response.ok) { const problem = await response.json(); throw new Error(typeof problem.detail === 'string' ? problem.detail : 'Request failed. Check the form and retry.'); }
        return response.json();
    }
    async function load() {
        cases = (await request('/api/cases')).items;
        const collected: Run[] = [];
        let offset = 0;
        let total = 1;
        while (offset < total) {
            const page = await request(`/api/history?limit=100&offset=${offset}`);
            collected.push(...page.items);
            offset += page.items.length;
            total = page.total;
            if (!page.items.length) break;
        }
        runs = collected.filter((item) => item.category === 'analysis' && item.status === 'completed');
    }
    function select(item: CaseRecord) { selected = item.id; status = item.status; note = ''; runId = ''; }
    async function create(event: SubmitEvent) {
        event.preventDefault(); busy = true; error = '';
        try { const created = await request('/api/cases', { company, reference, environment }); await load(); select(created); company = ''; reference = ''; }
        catch (problem) { error = String(problem); } finally { busy = false; }
    }
    async function update(event: SubmitEvent) {
        event.preventDefault(); busy = true; error = '';
        try { await request(`/api/cases/${selected}/updates`, { status, note, run_id: runId || null }); await load(); note = ''; runId = ''; }
        catch (problem) { error = String(problem); } finally { busy = false; }
    }
    onMount(() => { void load().catch((problem) => error = String(problem)); });
</script>

<svelte:head><title>Company cases — TraceLens</title></svelte:head>
<div class="space-y-6">
    <header><h2 class="text-2xl font-bold">Company cases</h2><p class="mt-2 text-slate-600">Continue a review without rerunning an analysis. Keep each saved result as a separate version.</p></header>
    <p class="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">Trusted local prototype only. Reviewed does not mean loan approved. Existing analysis runs are unassigned, not automatically real cases. Confirm company identity before linking a run; automatic identity matching is not performed.</p>
    {#if error}<p role="alert" class="rounded-xl bg-red-50 p-4 text-red-800">{error}</p>{/if}
    <details class="neo-card rounded-2xl p-5"><summary class="cursor-pointer font-semibold">+ Create company case</summary>
        <form onsubmit={create} class="mt-4 grid gap-4 sm:grid-cols-2">
            <label>Company name<input required maxlength="200" bind:value={company} class="mt-1 block w-full rounded-lg border p-3" /></label>
            <label>Registration / case reference<input maxlength="100" bind:value={reference} class="mt-1 block w-full rounded-lg border p-3" /></label>
            <label>Data category<select bind:value={environment} class="mt-1 block w-full rounded-lg border p-3"><option value="test">Test / synthetic</option><option value="real">Real / authorised documents</option></select></label>
            <button disabled={busy} class="neo-button self-end rounded-lg bg-brand-600 px-4 py-3 font-semibold text-white">Create case</button>
        </form>
    </details>
    <div class="grid items-start gap-6 lg:grid-cols-[minmax(260px,1fr)_2fr]">
        <aside class="neo-card space-y-4 rounded-2xl p-5">
            <label class="block text-sm">Find a company<input type="search" bind:value={search} class="mt-2 w-full rounded-lg border p-3" placeholder="Company or reference" /></label>
            {#each visible as item}<button onclick={() => select(item)} aria-pressed={selected === item.id} class="w-full rounded-xl border p-4 text-left {selected === item.id ? 'border-brand-600 bg-brand-50' : 'border-slate-200'}"><strong class="block">{item.company}</strong><span class="mt-1 block text-xs">{item.environment.toUpperCase()} · {labels[item.status]} · {item.runs.length} runs</span><span class="mt-1 block text-xs text-slate-500">{item.reference}</span></button>{/each}
            {#if !visible.length}<p class="text-sm text-slate-500">No cases yet. Create a test case, then explicitly link a saved analysis.</p>{/if}
        </aside>
        {#if active}
            <section class="neo-card space-y-6 rounded-2xl p-6">
                <div><span class="rounded-full bg-brand-100 px-3 py-1 text-xs font-semibold">{active.environment.toUpperCase()}</span><h3 class="mt-3 text-xl font-bold">{active.company}</h3><p class="mt-1 text-sm">{active.reference} · {labels[active.status]}</p></div>
                <div><h4 class="font-semibold">Saved analysis versions</h4><p class="mt-1 text-sm text-slate-500">Opening a result does not call AI or recalculate it.</p>
                    {#each active.runs as run, index}<a class="mt-3 block rounded-xl border border-slate-200 p-4 hover:bg-brand-50" href={`/?saved=${run.id}`}>Version {index + 1} · {run.document_count} documents · {new Date(run.created_at).toLocaleString()}<span class="mt-1 block text-sm font-semibold text-brand-700">Open full saved dashboard →</span></a>{/each}
                    {#if !active.runs.length}<p class="mt-3 text-sm">No analysis linked.</p>{/if}
                </div>
                <form onsubmit={update} class="space-y-4 border-t border-slate-200 pt-5">
                    <h4 class="font-semibold">Continue review</h4>
                    <label class="block text-sm">Review status<select bind:value={status} class="mt-1 block w-full rounded-lg border p-3">{#each Object.entries(labels) as [value, label]}<option {value}>{label}</option>{/each}</select></label>
                    <label class="block text-sm">Link an existing run (optional)<select bind:value={runId} class="mt-1 block w-full rounded-lg border p-3"><option value="">Do not link a run</option>{#each runs.filter((run) => !active?.runs.some((linked) => linked.id === run.id)) as run}<option value={run.id}>{run.title} · {new Date(run.created_at).toLocaleString()}</option>{/each}</select></label>
                    {#if runId}<a class="block text-sm text-brand-700 underline" href={`/?saved=${runId}`} target="_blank" rel="noreferrer">Inspect selected run before linking ↗</a>{/if}
                    <label class="block text-sm">Review note / documents requested<textarea bind:value={note} maxlength="6000" rows="4" class="mt-1 block w-full rounded-lg border p-3" placeholder="What did you check? What is still missing?"></textarea></label>
                    <button disabled={busy} class="neo-button rounded-lg bg-brand-600 px-4 py-3 font-semibold text-white">Save review update</button>
                </form>
                <div class="border-t border-slate-200 pt-5"><h4 class="font-semibold">Review timeline</h4>{#each [...active.events].reverse() as event}<div class="mt-3 border-l-2 border-brand-300 pl-4"><p class="text-xs text-slate-500">{new Date(event.at).toLocaleString()} · {labels[event.status]}</p><p class="mt-1 whitespace-pre-wrap break-words text-sm">{event.note || 'Status / analysis link updated.'}</p>{#if event.run_id}<a href={`/?saved=${event.run_id}`} class="text-sm text-brand-700 underline">Linked analysis</a>{/if}</div>{/each}</div>
            </section>
        {:else}<div class="rounded-2xl border border-dashed border-slate-300 p-10 text-center text-slate-500">Select a company case to continue its review.</div>{/if}
    </div>
</div>
