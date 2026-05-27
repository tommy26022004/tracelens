import type { AnalysisResponse, ChunkDetail } from './types';

/** Send a multi-PDF package to the backend analyser. */
export async function analyseApplication(files: File[]): Promise<AnalysisResponse> {
	const form = new FormData();
	for (const file of files) {
		form.append('files', file, file.name);
	}
	const res = await fetch('/api/applications/analyse', {
		method: 'POST',
		body: form
	});
	if (!res.ok) {
		const text = await res.text();
		throw new Error(`Analyse failed (${res.status}): ${text}`);
	}
	return (await res.json()) as AnalysisResponse;
}

/** Resolve a `{document_id}:{kind}:{index}` citation back to its source chunk. */
export async function fetchChunk(chunkId: string): Promise<ChunkDetail> {
	const parts = chunkId.split(':');
	if (parts.length < 3) {
		throw new Error(`Malformed chunk id: ${chunkId}`);
	}
	const index = parts[parts.length - 1];
	const kind = parts[parts.length - 2];
	const documentId = parts.slice(0, -2).join(':');
	const res = await fetch(
		`/api/applications/chunks/${encodeURI(documentId)}/${kind}/${index}`
	);
	if (!res.ok) {
		throw new Error(`Chunk lookup failed (${res.status})`);
	}
	return (await res.json()) as ChunkDetail;
}
