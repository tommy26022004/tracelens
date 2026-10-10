type DemoPdf = {
    name: string;
    pages: string[][];
};

const company = 'LOTUS TEST TRADING SDN BHD';

const demoDocuments: DemoPdf[] = [
    {
        name: 'demo_bank_statement.pdf',
        pages: [[
            'SYNTHETIC BANK - STATEMENT OF ACCOUNT',
            'SYNTHETIC TEST DATA - NOT AN OFFICIAL FINANCIAL DOCUMENT',
            'Bank Name: SYNTHETIC BANK',
            `Account Holder: ${company}`,
            'Account Number: TEST-ACCOUNT-001',
            'Statement Period: 01 Jan 2025 - 31 Jan 2025',
            'Date | Description | Debit | Credit | Balance',
            '01/01/2025 | CUSTOMER RECEIPT 01 | | 2,000.00 | 12,000.00',
            '04/01/2025 | OPERATING PAYMENT 02 | 1,200.00 | | 10,800.00',
            '07/01/2025 | CUSTOMER RECEIPT 03 | | 2,000.00 | 12,800.00',
            '10/01/2025 | OPERATING PAYMENT 04 | 1,200.00 | | 11,600.00',
            '13/01/2025 | CUSTOMER RECEIPT 05 | | 2,000.00 | 13,600.00',
            '16/01/2025 | OPERATING PAYMENT 06 | 1,200.00 | | 12,400.00',
            '19/01/2025 | CUSTOMER RECEIPT 07 | | 2,000.00 | 14,400.00',
            '22/01/2025 | OPERATING PAYMENT 08 | 1,200.00 | | 13,200.00',
            '25/01/2025 | CUSTOMER RECEIPT 09 | | 2,000.00 | 15,200.00',
            '28/01/2025 | OPERATING PAYMENT 10 | 1,200.00 | | 14,000.00',
            'Opening Balance: RM 10,000.00',
            'Total Credits: RM 10,000.00',
            'Total Debits: RM 6,000.00',
            'Closing Balance: RM 14,000.00'
        ]]
    },
    {
        name: 'demo_ssm_registration.pdf',
        pages: [[
            'SSM REGISTRATION - SYNTHETIC FORM 9',
            'SYNTHETIC TEST DATA - NOT AN OFFICIAL FINANCIAL DOCUMENT',
            'SURUHANJAYA SYARIKAT MALAYSIA - TEST FACSIMILE',
            `Company Name: ${company}`,
            'Registration Number: SYNTHETIC-REG-001',
            'Date of Incorporation: 15 January 2020',
            'Company Type: SDN BHD',
            'Business Address: 1 Fictional Test Road, Kuala Lumpur',
            'Paid-Up Capital: RM 50,000.00',
            'Directors:',
            '1. TEST DIRECTOR - NRIC: TEST-ID-001 - Role: Director'
        ]]
    },
    {
        name: 'demo_audited_financials.pdf',
        pages: [
            [
                company,
                'AUDITED FINANCIAL STATEMENTS - FICTIONAL TEST FIXTURE',
                'For the financial year ended 31 December 2025',
                'Audited by: FICTIONAL TEST AUDITOR (NO REAL AUDIT)',
                'Amounts in RM',
                'INCOME STATEMENT AND CASH FLOW',
                'Item | 2025 | 2024',
                'Revenue | 120,000.00 | 100,000.00',
                'Cost of Sales | 60,000.00 | 50,000.00',
                'Gross Profit | 60,000.00 | 50,000.00',
                'Operating Expenses | 30,000.00 | 26,000.00',
                'EBIT | 30,000.00 | 24,000.00',
                'Interest Expense | 3,000.00 | 2,000.00',
                'Net Profit | 21,600.00 | 17,600.00',
                'Cash from Operations | 28,000.00 | 22,000.00'
            ],
            [
                company,
                'AUDITED FINANCIAL STATEMENTS - FICTIONAL TEST FIXTURE',
                'For the financial year ended 31 December 2025',
                'Amounts in RM',
                'BALANCE SHEET',
                'Item | 2025 | 2024',
                'Current Assets | 80,000.00 | 65,000.00',
                'Non-Current Assets | 120,000.00 | 115,000.00',
                'Current Liabilities | 40,000.00 | 35,000.00',
                'Non-Current Liabilities | 60,000.00 | 55,000.00',
                'Total Equity | 100,000.00 | 90,000.00'
            ]
        ]
    },
    {
        name: 'demo_tax_return.pdf',
        pages: [[
            'FORM C - SYNTHETIC TAX RETURN',
            'SYNTHETIC TEST DATA - NOT AN OFFICIAL FINANCIAL DOCUMENT',
            'LEMBAGA HASIL DALAM NEGERI - TEST FACSIMILE',
            `Company Name: ${company}`,
            'Tax Reference Number: TEST-TAX-001',
            'Year of Assessment: 2025',
            'Gross Business Income: RM 120,000.00',
            'Chargeable Income: RM 27,000.00',
            'Tax Payable: RM 5,400.00',
            'Fixture amounts only; not a real tax calculation or filing.'
        ]]
    }
];

function escapePdfText(value: string): string {
    return value.replaceAll('\\', '\\\\').replaceAll('(', '\\(').replaceAll(')', '\\)');
}

function createPdf(pages: string[][]): ArrayBuffer {
    const objects: string[] = [];
    const pageIds = pages.map((_, index) => 4 + index * 2);
    objects[1] = '<< /Type /Catalog /Pages 2 0 R >>';
    objects[2] = `<< /Type /Pages /Kids [${pageIds.map((id) => `${id} 0 R`).join(' ')}] /Count ${pages.length} >>`;
    objects[3] = '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>';

    pages.forEach((lines, index) => {
        const pageId = pageIds[index];
        const contentId = pageId + 1;
        const commands = [
            'BT',
            '/F1 10 Tf',
            '50 790 Td',
            '14 TL',
            ...lines.flatMap((line) => [`(${escapePdfText(line)}) Tj`, 'T*']),
            'ET'
        ].join('\n');
        objects[pageId] = `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> /Contents ${contentId} 0 R >>`;
        objects[contentId] = `<< /Length ${new TextEncoder().encode(commands).length} >>\nstream\n${commands}\nendstream`;
    });

    let output = '%PDF-1.4\n';
    const offsets = [0];
    for (let id = 1; id < objects.length; id += 1) {
        offsets[id] = new TextEncoder().encode(output).length;
        output += `${id} 0 obj\n${objects[id]}\nendobj\n`;
    }
    const xrefOffset = new TextEncoder().encode(output).length;
    output += `xref\n0 ${objects.length}\n0000000000 65535 f \n`;
    for (let id = 1; id < objects.length; id += 1) {
        output += `${String(offsets[id]).padStart(10, '0')} 00000 n \n`;
    }
    output += `trailer\n<< /Size ${objects.length} /Root 1 0 R >>\nstartxref\n${xrefOffset}\n%%EOF\n`;
    const bytes = new TextEncoder().encode(output);
    return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer;
}

export function createDemoPackage(): File[] {
    return demoDocuments.map((document) => new File(
        [createPdf(document.pages)],
        document.name,
        { type: 'application/pdf', lastModified: 0 }
    ));
}
