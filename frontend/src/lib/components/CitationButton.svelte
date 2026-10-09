<script lang="ts">
    import { citationLabel, citationTitle } from '../citations';
    import type { CitationReference } from '../types';

    interface Props {
        chunkId: string;
        references: Record<string, CitationReference>;
        onCitationClick: (chunkId: string) => void;
    }

    let { chunkId, references, onCitationClick }: Props = $props();
</script>

<button
    type="button"
    class="citation"
    title={citationTitle(chunkId, references)}
    aria-label={`View source ${citationLabel(chunkId, references)}: ${citationTitle(chunkId, references)}`}
    onclick={() => onCitationClick(chunkId)}
>
    {citationLabel(chunkId, references)}
</button>
