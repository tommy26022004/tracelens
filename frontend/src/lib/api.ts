import type { AnalysisJobResponse, AnalysisResponse, ChunkDetail } from './types';

export interface AnalysisProgress {
	progress: number;
	phase: string;
}

function friendlyAnalysisError(message: string): string {
	if (message.includes('RESOURCE_EXHAUSTED') || message.includes('429')) {
		return 'The Gemini daily quota is currently exhausted. Please retry later or use the deterministic fallback mode.';
	}
	if (message.toLowerCase().includes('failed to fetch')) {
		return 'The backend is unavailable. Check that the Docker services are running, then try again.';
	}
	return message;
}

/** Send a multi-PDF package to the backend analyser. */
export async function analyseApplication(
	files: File[],
	onProgress?: (update: AnalysisProgress) => void
): Promise<AnalysisResponse> {
	const form = new FormData();
	for (const file of files) {
		form.append('files', file, file.name);
	}
	const res = await fetch('/api/applications/analyse/jobs', {
		method: 'POST',
		body: form
	});
	if (!res.ok) {
		const text = await res.text();
		throw new Error(`Analyse failed (${res.status}): ${text}`);
	}
	let job = (await res.json()) as AnalysisJobResponse;
	onProgress?.({ progress: job.progress, phase: job.phase });
	for (let attempt = 0; attempt < 1200; attempt += 1) {
		if (job.status === 'completed' && job.result) return job.result;
		if (job.status === 'failed') {
			throw new Error(friendlyAnalysisError(job.error ?? 'Analysis job failed'));
		}
		await new Promise((resolve) => setTimeout(resolve, 500));
		const statusResponse = await fetch(`/api/applications/analyse/jobs/${job.job_id}`);
		if (!statusResponse.ok) {
			throw new Error(`Job status failed (${statusResponse.status})`);
		}
		job = (await statusResponse.json()) as AnalysisJobResponse;
		onProgress?.({ progress: job.progress, phase: job.phase });
	}
	throw new Error('Analysis timed out after 10 minutes');
}

/** Resolve a `{document_id}:{kind}:{index}` citation back to its source chunk. */
export async function fetchChunk(chunkId: string, applicationId?: string): Promise<ChunkDetail> {
	const parts = chunkId.split(':');
	if (parts.length < 3) {
		throw new Error(`Malformed chunk id: ${chunkId}`);
	}
	const index = parts[parts.length - 1];
	const kind = parts[parts.length - 2];
	const documentId = parts.slice(0, -2).join(':');
	const res = await fetch(
        `/api/applications/chunks/${documentId.split('/').map(encodeURIComponent).join('/')}/${kind}/${index}` +
        (applicationId ? `?application_id=${encodeURIComponent(applicationId)}` : '')
	);
	if (!res.ok) {
		throw new Error(`Chunk lookup failed (${res.status})`);
	}
	return (await res.json()) as ChunkDetail;
}
