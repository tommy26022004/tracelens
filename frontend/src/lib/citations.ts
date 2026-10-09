/** Split a text into alternating prose / citation segments.
 *
 * Citations match `[chunk_id]` where chunk_id looks like
 * `someprefix/optional/path:kind:index`. LLMs occasionally comma-join
 * several ids inside one bracket pair — we split those into separate
 * citation segments so each one is individually clickable.
 */
import type { CitationReference } from './types';

const CITATION_RE =
    /\[([^\[\]]*?:(?:summary|transaction|director|period|page):\d+(?:\s*[,;]\s*[^\[\]]*?:(?:summary|transaction|director|period|page):\d+)*)\]/g;

export function citationTitle(chunkId: string, references: Record<string, CitationReference>): string {
    const reference = references[chunkId];
    if (!reference) {
        return chunkId.split(':').slice(0, -2).join(':').split('/').at(-1) ?? 'Source';
    }
    const pages = reference.pages.length
        ? `${reference.pages.length > 1 ? 'pp.' : 'p.'} ${reference.pages.join(', ')}`
        : 'page reference unavailable';
    return `${reference.filename} · ${pages}`;
}

export function citationLabel(chunkId: string, references: Record<string, CitationReference>): string {
    const index = Object.keys(references).indexOf(chunkId);
    return index >= 0 ? `[${index + 1}]` : 'Source';
}

export type Segment =
	| { kind: 'text'; value: string }
	| { kind: 'citation'; chunkId: string };

export type DisplaySegment =
    | { kind: 'text'; value: string }
    | { kind: 'sources'; chunkIds: string[] };

export function groupCitations(text: string): DisplaySegment[] {
    const segments = segmentise(text);
    const grouped: DisplaySegment[] = [];
    for (let index = 0; index < segments.length; index++) {
        const segment = segments[index];
        if (segment.kind === 'text') {
            grouped.push(segment);
            continue;
        }
        const chunkIds = [segment.chunkId];
        while (index + 1 < segments.length) {
            const next = segments[index + 1];
            if (next.kind === 'citation') {
                chunkIds.push(next.chunkId);
                index++;
            } else if (!next.value.trim() && segments[index + 2]?.kind === 'citation') {
                index++;
            } else {
                break;
            }
        }
        grouped.push({ kind: 'sources', chunkIds: [...new Set(chunkIds)] });
    }
    return grouped;
}

export function segmentise(text: string): Segment[] {
	const out: Segment[] = [];
    let cursor = 0;
    const adjacentIds = new Set<string>();
	for (const match of text.matchAll(CITATION_RE)) {
		const start = match.index ?? 0;
        if (start > cursor) {
            if (text.slice(cursor, start).trim()) adjacentIds.clear();
			out.push({ kind: 'text', value: text.slice(cursor, start) });
		}
		for (const id of match[1].split(/\s*[,;]\s*/)) {
			const trimmed = id.trim();
            if (trimmed && !adjacentIds.has(trimmed)) {
                out.push({ kind: 'citation', chunkId: trimmed });
                adjacentIds.add(trimmed);
			}
		}
		cursor = start + match[0].length;
	}
	if (cursor < text.length) {
		out.push({ kind: 'text', value: text.slice(cursor) });
	}
	return out;
}
