export function assessmentParagraphs(body: string): string[] {
    return body.replace(/\*\*(Character|Capacity|Capital|Collateral|Conditions)(:?)\*\*/g, '$1$2').split(/\n\s*\n/).flatMap((block) => block.trim().split(
        /(?<=[.!?])\s+(?=(?:(?:Finally|Similarly|However),\s+)?(?:The\s+)?['"‘“]?(?:Character|Capacity|Capital|Collateral|Conditions)['"’”]?\s+(?:assessment\s+)?(?:is|are)\b)/
    )).flatMap((block) => block.split(/(?<=[.!?])\s+(?=(?:For the financial year|Key financial ratios|The Interest Coverage Ratio|Total equity for|The capital aspect)\b)/)).filter(Boolean);
}

export function assessmentHeading(paragraph: string): string {
    if (paragraph.startsWith('System validation checks:')) return 'System checks';
    const labelled = paragraph.match(/^(Character|Capacity|Capital|Collateral|Conditions)\s*:/);
    if (labelled) return labelled[1];
    const criterion = paragraph.match(/^(?:(?:Finally|Similarly|However),\s+)?(?:The\s+)?['"‘“]?(Character|Capacity|Capital|Collateral|Conditions)['"’”]?\s+(?:assessment\s+)?(?:is|are)\b/);
    return criterion?.[1] ?? 'Assessment detail';
}

export function assessmentGroupHeading(paragraph: string): string | null {
    const label = paragraph.trim().replace(/^#{1,6}\s+/, '').replace(/\*\*/g, '').replace(/:\s*$/, '').trim();
    return /^(?:Provisional\s+)?5C\s+(?:credit\s+)?assessment$/i.test(label) ? label : null;
}

export function retrievalLabel(status?: string): string {
    return status === 'complete' ? 'Available-source search finished' : status?.replaceAll('_', ' ') ?? 'Not available';
}

export function humanChecksForDisplay(checks: string[], findingCodes: string[]): string[] {
    const seen = new Set<string>();
    const codePattern = findingCodes.length
        ? new RegExp(`^(?:${findingCodes.map((code) => code.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})\\s*:`, 'i')
        : null;
    return checks.filter((rawCheck) => {
        const check = rawCheck.trim();
        if (!check || codePattern?.test(check)) return false;
        const lowered = check.toLowerCase();
        const category = lowered.includes('repayment') || lowered.includes('debt service')
            ? 'repayment'
            : lowered.includes('bank statement') || lowered.includes('banking history')
              ? 'bank_evidence'
              : lowered.includes('audited financial')
                ? 'audited_financials'
                : lowered.includes('ssm') || lowered.includes('registration status')
                  ? 'registration'
                  : ['collateral', 'facility statement', 'security document'].some((term) => lowered.includes(term))
                    ? 'collateral'
                    : lowered.includes('management account') || lowered.includes('industry condition')
                      ? 'conditions'
                      : lowered.replace(/[^a-z0-9]+/g, ' ').trim();
        if (seen.has(category)) return false;
        seen.add(category);
        return true;
    });
}
