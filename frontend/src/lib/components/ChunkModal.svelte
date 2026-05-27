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
</script>

{#if chunkId}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 px-4"
		onclick={onClose}
		onkeydown={(e) => e.key === 'Escape' && onClose()}
		role="dialog"
		tabindex="-1"
	>
		<div
			class="w-full max-w-xl rounded-xl bg-white p-6 shadow-2xl"
			onclick={(e) => e.stopPropagation()}
			role="document"
		>
			<div class="flex items-start justify-between gap-4">
				<div>
					<h3 class="text-sm font-semibold text-slate-500 uppercase tracking-wide">
						Source citation
					</h3>
					<p class="mt-1 font-mono text-xs text-slate-700 break-all">{chunkId}</p>
				</div>
				<button
					type="button"
					class="rounded-md p-1 text-slate-500 hover:bg-slate-100"
					onclick={onClose}
					aria-label="Close"
				>
					×
				</button>
			</div>

			<div class="mt-4 border-t border-slate-100 pt-4">
				{#if loading}
					<p class="text-sm text-slate-500">Loading source…</p>
				{:else if error}
					<p class="text-sm text-red-600">{error}</p>
				{:else if chunk}
					<dl class="grid grid-cols-3 gap-2 text-sm">
						<dt class="font-medium text-slate-500">Kind</dt>
						<dd class="col-span-2 text-slate-900">{chunk.kind}</dd>
						<dt class="font-medium text-slate-500">Page</dt>
						<dd class="col-span-2 text-slate-900">{chunk.page}</dd>
					</dl>
					<div class="mt-4">
						<p class="text-xs font-medium text-slate-500 uppercase">Source text</p>
						<p
							class="mt-1 rounded-md bg-slate-50 p-3 text-sm text-slate-800 ring-1 ring-slate-200"
						>
							{chunk.text}
						</p>
					</div>
					{#if Object.keys(chunk.source_metadata ?? {}).length > 0}
						<details class="mt-4">
							<summary class="cursor-pointer text-xs font-medium text-slate-500">
								Raw metadata
							</summary>
							<pre
								class="mt-2 max-h-48 overflow-auto rounded-md bg-slate-900 p-3 text-xs text-slate-100">{JSON.stringify(
									chunk.source_metadata,
									null,
									2
								)}</pre>
						</details>
					{/if}
				{/if}
			</div>
		</div>
	</div>
{/if}
