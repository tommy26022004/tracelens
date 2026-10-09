<script lang="ts">
    import { groupCitations } from '../citations';
    import CitationButton from './CitationButton.svelte';
    import type { CitationReference } from '../types';

	interface Props {
        text: string;
        references?: Record<string, CitationReference>;
		onCitationClick: (chunkId: string) => void;
	}

    let { text, references = {}, onCitationClick }: Props = $props();
	const segments = $derived(groupCitations(text));
	let expanded = $state<Record<number, boolean>>({});
	$effect(() => { text; expanded = {}; });
</script>

<span>
	{#each segments as seg, i (i)}
		{#if seg.kind === 'text'}
			<span>{seg.value}</span>
		{:else if seg.chunkIds.length === 1}
            <CitationButton chunkId={seg.chunkIds[0]} {references} {onCitationClick} />
		{:else}
			<span class="inline-block align-baseline">
				<button type="button" aria-expanded={!!expanded[i]} onclick={() => expanded[i] = !expanded[i]} class="mx-1 cursor-pointer rounded bg-brand-50 px-2 py-0.5 text-xs font-semibold text-brand-800">{expanded[i] ? 'Hide' : 'View'} {seg.chunkIds.length} sources</button>
				{#if expanded[i]}
				<span class="inline-flex flex-wrap gap-1 rounded border border-slate-200 bg-white p-2">
					{#each seg.chunkIds as chunkId (chunkId)}<CitationButton {chunkId} {references} {onCitationClick} />{/each}
				</span>
				{/if}
			</span>
		{/if}
	{/each}
</span>
