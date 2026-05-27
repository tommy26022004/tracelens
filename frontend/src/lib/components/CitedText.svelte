<script lang="ts">
	import { segmentise } from '../citations';

	interface Props {
		text: string;
		onCitationClick: (chunkId: string) => void;
	}

	let { text, onCitationClick }: Props = $props();
	const segments = $derived(segmentise(text));
</script>

<span>
	{#each segments as seg, i (i)}
		{#if seg.kind === 'text'}
			<span>{seg.value}</span>
		{:else}
			<button
				type="button"
				class="citation"
				title="View source: {seg.chunkId}"
				onclick={() => onCitationClick(seg.chunkId)}
			>
				{seg.chunkId.split(':').slice(-2).join(':')}
			</button>
		{/if}
	{/each}
</span>
