<script lang="ts">
    import type { ChunkDetail } from '../types';

    interface Props {
        chunkId: string | null;
        chunk: ChunkDetail | null;
        loading: boolean;
        error: string | null;
        onClose: () => void;
    }

    let { chunkId, chunk, loading, error, onClose }: Props = $props();
    let selectedPage: number | null = $state(null);
    let previewFailed = $state(false);
    let dialog: HTMLDialogElement | undefined = $state();

    $effect(() => {
        if (chunkId && dialog && !dialog.open) dialog.showModal();
    });

    $effect(() => {
        selectedPage = chunk?.source_pages?.[0] ?? null;
        previewFailed = false;
    });

    function selectPage(page: number) {
        selectedPage = page;
        previewFailed = false;
    }

    function closeFromBackdrop(event: MouseEvent) {
        if (event.target === event.currentTarget) onClose();
    }
</script>

{#if chunkId}
    <dialog
        bind:this={dialog}
        class="fixed inset-y-0 left-auto right-0 m-0 h-dvh max-h-none w-full max-w-3xl border-0 bg-white p-0 shadow-2xl backdrop:bg-slate-900/30"
        onclick={closeFromBackdrop}
        oncancel={(event) => { event.preventDefault(); onClose(); }}
        aria-label="Source citation"
    >
        <div class="flex h-full w-full flex-col overflow-hidden bg-white" role="document">
            <div class="flex items-start justify-between gap-4 border-b border-slate-200 px-6 py-4">
                <div class="min-w-0">
                    <h3 class="text-xs font-semibold uppercase tracking-wide text-slate-500">Source citation</h3>
                    <p class="mt-1 break-words text-base font-semibold text-slate-900">{chunk?.filename ?? 'Loading document…'}</p>
                </div>
                <button type="button" class="rounded-md px-2 py-1 text-xl text-slate-500 hover:bg-slate-100" onclick={onClose} aria-label="Close">×</button>
            </div>

            {#if loading}
                <p class="p-6 text-sm text-slate-500">Loading source…</p>
            {:else if error}
                <p class="p-6 text-sm text-red-600">{error}</p>
            {:else if chunk}
                <div class="min-h-0 overflow-auto">
                    <div class="space-y-5 overflow-auto p-6">
                        {#if chunk.source_pages.length > 0}
                            <div>
                                <p class="text-xs font-semibold uppercase text-slate-500">Supporting pages</p>
                                <div class="mt-2 flex flex-wrap gap-2">
                                    {#each chunk.source_pages as page (page)}
                                        <button
                                            type="button"
                                            class="rounded-md border px-3 py-1 text-sm {selectedPage === page ? 'border-brand-600 bg-brand-50 text-brand-700' : 'border-slate-200 text-slate-700'}"
                                            aria-pressed={selectedPage === page}
                                            onclick={() => selectPage(page)}
                                        >Page {page}</button>
                                    {/each}
                                </div>
                                {#if chunk.source_pages.length > 1}
                                    <p class="mt-2 text-xs text-slate-500">This reference combines evidence from multiple pages.</p>
                                {/if}
                            </div>
                        {:else}
                            <p class="rounded-md bg-amber-50 p-3 text-sm text-amber-900">The page reference has not been verified. Re-analyse this package to capture source locations.</p>
                        {/if}

                        {#if chunk.pdf_url}
                            <a class="inline-block text-sm font-semibold text-brand-700 hover:underline" href={chunk.pdf_url + (selectedPage ? '#page=' + selectedPage : '')} target="_blank" rel="noreferrer">Open original PDF ↗</a>
                        {:else}
                            <p class="rounded-md bg-amber-50 p-3 text-sm text-amber-900">The original PDF is unavailable for this older result. Re-upload the package to preserve its source files.</p>
                        {/if}

                        <details>
                            <summary class="cursor-pointer text-sm font-semibold text-slate-600">Extracted context</summary>
                            <p class="mt-2 whitespace-pre-line rounded-md bg-slate-50 p-3 text-sm leading-relaxed text-slate-800">{chunk.text}</p>
                        </details>

                        {#if chunk.source_locations.length > 0}
                            <div>
                                <p class="text-xs font-semibold uppercase text-slate-500">Source text · Page {selectedPage}</p>
                                <ul class="mt-2 space-y-2">
                                    {#each chunk.source_locations.filter((location) => location.page === selectedPage) as location, index (index)}
                                        <li class="rounded-md border border-slate-200 p-3 text-xs text-slate-700">
                                            <span class="mb-1 block font-medium text-slate-500">{location.field.replaceAll('_', ' ')}</span>
                                            {location.text}
                                        </li>
                                    {/each}
                                </ul>
                            </div>
                        {/if}

                        <details>
                            <summary class="cursor-pointer text-xs text-slate-500">Technical reference</summary>
                            <p class="mt-2 break-all font-mono text-xs text-slate-600">{chunkId}</p>
                        </details>
                    </div>
                    <div class="min-h-80 overflow-auto bg-slate-100 p-4">
                        {#if chunk.preview_url && selectedPage}
                            {#if previewFailed}
                                <p class="p-4 text-sm text-red-700">Unable to load this page preview. Use “Open original PDF” to inspect the source.</p>
                            {:else}
                                <img
                                    class="mx-auto w-full bg-white shadow"
                                    src={chunk.preview_url + '/' + selectedPage}
                                    alt={chunk.filename + ', page ' + selectedPage}
                                    onerror={() => previewFailed = true}
                                />
                            {/if}
                        {:else}
                            <p class="p-4 text-sm text-slate-500">A verified original page will appear here when available.</p>
                        {/if}
                    </div>
                </div>
            {/if}
        </div>
    </dialog>
{/if}
