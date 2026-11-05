import type { AnalysisResponse, PackageInventory } from './types';

export interface ReadinessAction {
    id: string;
    title: string;
    detail: string;
    dimensions: string[];
}

const documentGuidance: Record<string, { label: string; dimensions: string[] }> = {
    bank_statement: { label: 'bank statements', dimensions: ['Character', 'Capacity'] },
    audited_financials: { label: 'audited financial statements', dimensions: ['Capacity', 'Capital'] },
    ssm_registration: { label: 'SSM registration', dimensions: ['Character'] },
    tax_return: { label: 'tax return', dimensions: ['Character', 'Conditions'] }
};

export function buildReadinessActions(result: Pick<AnalysisResponse, 'package_inventory' | 'ratios'>): ReadinessAction[] {
    const inventory = result.package_inventory as PackageInventory;
    if (!Array.isArray(inventory.documents)) return [];
    const actions: ReadinessAction[] = [];

    for (const kind of inventory.missing_core_kinds ?? []) {
        const guidance = documentGuidance[kind];
        actions.push({
            id: `missing-${kind}`,
            title: `Request ${guidance?.label ?? kind.replaceAll('_', ' ')}`,
            detail: 'The package inventory does not contain this core document type. Confirm whether it is required and obtain it before relying on the assessment.',
            dimensions: guidance?.dimensions ?? []
        });
    }
    if (inventory.missing_bank_months?.length) {
        actions.push({
            id: 'bank-coverage',
            title: `Review ${inventory.missing_bank_months.length} missing bank month${inventory.missing_bank_months.length === 1 ? '' : 's'}`,
            detail: `No statement coverage was identified for ${inventory.missing_bank_months.join(', ')}. Request missing statements or confirm the review period.`,
            dimensions: ['Character', 'Capacity']
        });
    }
    if (inventory.failed_documents > 0) {
        actions.push({
            id: 'failed-documents',
            title: `Resolve ${inventory.failed_documents} unprocessed document${inventory.failed_documents === 1 ? '' : 's'}`,
            detail: 'Inspect extraction errors and re-upload readable source PDFs where necessary.',
            dimensions: []
        });
    }
    if (inventory.duplicate_document_ids?.length) {
        actions.push({
            id: 'duplicates',
            title: `Review ${inventory.duplicate_document_ids.length} duplicate upload${inventory.duplicate_document_ids.length === 1 ? '' : 's'}`,
            detail: 'Confirm whether the repeated PDFs are intentional before counting them as separate evidence.',
            dimensions: []
        });
    }
    const financials = result.ratios?.financial_ratios ?? [];
    if (financials.some((period) => period.dsr?.value == null)) {
        actions.push({
            id: 'repayment-schedule',
            title: 'Verify debt-service obligations',
            detail: 'Debt-service coverage is unavailable for at least one period. Obtain the actual repayment schedule rather than estimating principal payments from liabilities.',
            dimensions: ['Capacity']
        });
    }
    return actions;
}
