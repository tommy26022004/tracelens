/** Split a text into alternating prose / citation segments.
 *
 * Citations match `[chunk_id]` where chunk_id looks like
 * `someprefix/optional/path:kind:index`. LLMs occasionally comma-join
 * several ids inside one bracket pair — we split those into separate
 * citation segments so each one is individually clickable.
 */
const CITATION_RE =
	/\[([^\[\]]*?:(?:summary|transaction|director|period):\d+(?:\s*[,;]\s*[^\[\]]*?:(?:summary|transaction|director|period):\d+)*)\]/g;

export type Segment =
	| { kind: 'text'; value: string }
	| { kind: 'citation'; chunkId: string };

export function segmentise(text: string): Segment[] {
	const out: Segment[] = [];
	let cursor = 0;
	for (const match of text.matchAll(CITATION_RE)) {
		const start = match.index ?? 0;
		if (start > cursor) {
			out.push({ kind: 'text', value: text.slice(cursor, start) });
		}
		for (const id of match[1].split(/\s*[,;]\s*/)) {
			const trimmed = id.trim();
			if (trimmed) {
				out.push({ kind: 'citation', chunkId: trimmed });
			}
		}
		cursor = start + match[0].length;
	}
	if (cursor < text.length) {
		out.push({ kind: 'text', value: text.slice(cursor) });
	}
	return out;
}
