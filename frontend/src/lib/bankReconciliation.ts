export function bankReconciliation(metric: { total_credits: string; total_debits: string; net_change: string }) {
    const credits = Math.round(Number(metric.total_credits) * 100);
    const debits = Math.round(Number(metric.total_debits) * 100);
    const change = Math.round(Number(metric.net_change) * 100);
    const valid = [credits, debits, change].every(Number.isSafeInteger);
    const movement = credits - debits;
    const difference = change - movement;
    return {
        movement: valid ? (movement / 100).toFixed(2) : null,
        difference: valid ? (difference / 100).toFixed(2) : null,
        mismatch: valid ? difference !== 0 : true
    };
}
