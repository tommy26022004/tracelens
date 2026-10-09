<script lang="ts">
	import { retrievalLabel } from '../assessmentText';
	import type { CitationReference, RetrievalBundle } from '../types';
	import CitationButton from './CitationButton.svelte';

	interface Props {
		retrieval: RetrievalBundle;
		references: Record<string, CitationReference>;
		onCitationClick: (chunkId: string) => void;
	}

	let { retrieval, references, onCitationClick }: Props = $props();
</script>

<details class="neo-card rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
	<summary class="cursor-pointer text-sm font-semibold text-slate-900">
		RAG evidence · {retrieval.evidence.length} excerpts · {retrievalLabel(retrieval.status)}
	</summary>
	<div class="mt-4 space-y-4 text-sm">
		<p class="text-sm text-slate-600">Search completion applies only to available sources. Missing document categories can still prevent a full 5C assessment.</p>
		<p class="text-xs text-slate-500">
			Retrieval mode: {retrieval.embedding_space}.
			{#if retrieval.embedding_space.startsWith('local-hash')}
				Local lexical hashing, not a semantic embedding model.
			{/if}
			Similarity scores are not confidence scores or credit ratings.
		</p>
		<p class="text-xs text-slate-500">Evidence supplied to: {retrieval.consumed_by.join(', ')}. Retrieved excerpts are candidates for human verification, not verified facts.</p>
		{#each retrieval.warnings as warning, index (index)}
			<p class="rounded-md bg-amber-50 p-3 text-amber-900">{warning}</p>
		{/each}
		<div class="grid min-w-0 auto-rows-auto items-start gap-3 md:grid-cols-2" data-testid="retrieval-topics">
			{#each retrieval.queries as query, index (index)}
				<div class="min-w-0 rounded-lg border border-slate-200 p-3 [overflow-wrap:anywhere]" data-testid="retrieval-topic">
					<p class="font-semibold text-slate-800">{query.topic} · {query.status.replaceAll('_', ' ')}</p>
					<p class="mt-1 text-xs text-slate-500">{query.query}</p>
					<div class="mt-2 flex flex-wrap gap-1">
						{#each query.selected_chunk_ids as chunkId (chunkId)}
							<CitationButton {chunkId} {references} {onCitationClick} />
						{/each}
					</div>
				</div>
			{/each}
		</div>
		{#if retrieval.evidence.length === 0}
			<p class="rounded-md bg-amber-50 p-3 text-amber-900">No suitable excerpts were retrieved. This does not mean that no risk exists; inspect the original documents.</p>
		{/if}
		{#each retrieval.evidence as evidence (evidence.chunk_id)}
			<details class="rounded-lg border border-slate-200 p-3">
				<summary class="cursor-pointer text-slate-700">{evidence.filename} · page {evidence.pages.join(', ')} · similarity {evidence.score.toFixed(3)}</summary>
				<div class="mt-2 flex items-center gap-2">
					<CitationButton chunkId={evidence.chunk_id} {references} {onCitationClick} />
					<span class="text-xs text-slate-500">{evidence.evidence_type.replaceAll('_', ' ')}</span>
				</div>
				<p class="mt-2 whitespace-pre-wrap break-words text-xs leading-relaxed text-slate-600">{evidence.text}</p>
				{#if evidence.truncated}<p class="mt-2 text-xs text-amber-700">Excerpt truncated to fit the evidence budget. Open the source for the full page.</p>{/if}
			</details>
		{/each}
	</div>
</details>
