type DemoPdf = {
    name: string;
    pages: () => string[];
};

type PdfColor = [number, number, number];
type PdfFont = 'regular' | 'bold';

const company = 'LOTUS TEST TRADING SDN BHD';
const syntheticDisclaimer = 'SYNTHETIC TEST DATA - NOT AN OFFICIAL FINANCIAL DOCUMENT';
const pageWidth = 595;
const pageHeight = 842;
const navy: PdfColor = [0.055, 0.153, 0.278];
const navyMuted: PdfColor = [0.12, 0.22, 0.35];
const olive: PdfColor = [0.373, 0.435, 0.247];
const amber: PdfColor = [0.91, 0.58, 0.16];
const ink: PdfColor = [0.08, 0.12, 0.2];
const slate: PdfColor = [0.34, 0.39, 0.46];
const line: PdfColor = [0.82, 0.85, 0.88];
const soft: PdfColor = [0.96, 0.97, 0.98];
const white: PdfColor = [1, 1, 1];

function escapePdfText(value: string): string {
    return value.replaceAll('\\', '\\\\').replaceAll('(', '\\(').replaceAll(')', '\\)');
}

function color(value: PdfColor): string {
    return value.map((channel) => channel.toFixed(3)).join(' ');
}

function estimateWidth(value: string, size: number): number {
    return value.length * size * 0.5;
}

function addText(
    commands: string[],
    value: string,
    x: number,
    y: number,
    size = 10,
    font: PdfFont = 'regular',
    fill: PdfColor = ink,
    align: 'left' | 'right' | 'center' = 'left'
): void {
    const width = estimateWidth(value, size);
    const adjustedX = align === 'right' ? x - width : align === 'center' ? x - width / 2 : x;
    commands.push(`BT /${font === 'bold' ? 'F2' : 'F1'} ${size} Tf ${color(fill)} rg 1 0 0 1 ${adjustedX.toFixed(1)} ${y.toFixed(1)} Tm (${escapePdfText(value)}) Tj ET`);
}

function addRect(
    commands: string[],
    x: number,
    y: number,
    width: number,
    height: number,
    fill: PdfColor,
    stroke?: PdfColor,
    strokeWidth = 1
): void {
    commands.push('q');
    commands.push(`${color(fill)} rg`);
    if (stroke) commands.push(`${color(stroke)} RG ${strokeWidth} w`);
    commands.push(`${x} ${y} ${width} ${height} re ${stroke ? 'B' : 'f'}`);
    commands.push('Q');
}

function addLine(commands: string[], x1: number, y1: number, x2: number, y2: number, stroke: PdfColor = line, width = 1): void {
    commands.push(`q ${color(stroke)} RG ${width} w ${x1} ${y1} m ${x2} ${y2} l S Q`);
}

function addPageChrome(
    commands: string[],
    documentCode: string,
    title: string,
    subtitle: string,
    pageNumber: number,
    totalPages: number
): void {
    addRect(commands, 0, 762, pageWidth, 80, navy);
    addRect(commands, 0, 762, 12, 80, olive);
    addText(commands, 'TRACELENS', 42, 808, 14, 'bold', white);
    addText(commands, 'RECRUITER DEMO PACKAGE', 42, 789, 7.5, 'bold', [0.76, 0.82, 0.89]);
    addText(commands, documentCode, 553, 807, 8, 'bold', white, 'right');
    addText(commands, syntheticDisclaimer, 553, 790, 5.5, 'bold', [0.96, 0.73, 0.38], 'right');
    addText(commands, title, 42, 724, 22, 'bold', ink);
    addText(commands, subtitle, 42, 702, 9.5, 'regular', slate);
    addLine(commands, 42, 55, 553, 55);
    addText(commands, 'TraceLens demo document | Fictitious company and amounts | Human review required', 42, 34, 7.5, 'regular', slate);
    addText(commands, `Page ${pageNumber} of ${totalPages}`, 553, 34, 7.5, 'bold', slate, 'right');
}

function addInfoRow(commands: string[], label: string, value: string, x: number, y: number, width = 511): void {
    addRect(commands, x, y - 9, width, 27, white, line, 0.7);
    addRect(commands, x, y - 9, 158, 27, soft);
    addText(commands, label, x + 12, y, 7.5, 'bold', slate);
    addText(commands, value, x + 174, y, 9, 'bold', ink);
}

function addSectionLabel(commands: string[], value: string, y: number): void {
    addRect(commands, 42, y - 5, 5, 18, olive);
    addText(commands, value.toUpperCase(), 58, y, 8, 'bold', navyMuted);
    addLine(commands, 58, y - 8, 553, y - 8, line, 0.7);
}

function addTableHeader(commands: string[], labels: string[], columns: number[], y: number, rightFrom = 2): void {
    addRect(commands, 42, y - 8, 511, 27, navyMuted);
    labels.forEach((label, index) => addText(commands, label.toUpperCase(), columns[index], y, 7.5, 'bold', white, index >= rightFrom ? 'right' : 'left'));
}

function addTableRow(
    commands: string[],
    values: string[],
    columns: number[],
    y: number,
    shaded: boolean,
    bold = false,
    rightFrom = 2
): void {
    addRect(commands, 42, y - 8, 511, 25, shaded ? soft : white, line, 0.45);
    values.forEach((value, index) => addText(commands, value, columns[index], y, 8, bold ? 'bold' : 'regular', ink, index >= rightFrom ? 'right' : 'left'));
}

function addMetricCard(commands: string[], label: string, value: string, x: number, y: number, width: number): void {
    addRect(commands, x, y, width, 55, white, line, 0.7);
    addText(commands, label.toUpperCase(), x + 12, y + 35, 7, 'bold', slate);
    addText(commands, value, x + 12, y + 14, 12, 'bold', navy);
}

function buildBankStatement(): string[] {
    const commands: string[] = [];
    addPageChrome(commands, 'BANK / JAN-2025', 'Statement of Account', 'Monthly operating account activity and reconciled balances', 1, 1);
    addInfoRow(commands, 'Account Holder:', company, 42, 659);
    addInfoRow(commands, 'Account Number:', 'TEST-ACCOUNT-001', 42, 629);
    addInfoRow(commands, 'Statement Period:', '01 Jan 2025 - 31 Jan 2025', 42, 599);
    addSectionLabel(commands, 'Transaction activity', 558);
    const columns = [52, 116, 385, 456, 543];
    addTableHeader(commands, ['Date', 'Description', 'Debit (RM)', 'Credit (RM)', 'Balance (RM)'], columns, 530);
    const rows = [
        ['01/01/2025', 'CUSTOMER RECEIPT 01', '-', '2,000.00', '12,000.00'],
        ['04/01/2025', 'OPERATING PAYMENT 02', '1,200.00', '-', '10,800.00'],
        ['07/01/2025', 'CUSTOMER RECEIPT 03', '-', '2,000.00', '12,800.00'],
        ['10/01/2025', 'OPERATING PAYMENT 04', '1,200.00', '-', '11,600.00'],
        ['13/01/2025', 'CUSTOMER RECEIPT 05', '-', '2,000.00', '13,600.00'],
        ['16/01/2025', 'OPERATING PAYMENT 06', '1,200.00', '-', '12,400.00'],
        ['19/01/2025', 'CUSTOMER RECEIPT 07', '-', '2,000.00', '14,400.00'],
        ['22/01/2025', 'OPERATING PAYMENT 08', '1,200.00', '-', '13,200.00'],
        ['25/01/2025', 'CUSTOMER RECEIPT 09', '-', '2,000.00', '15,200.00'],
        ['28/01/2025', 'OPERATING PAYMENT 10', '1,200.00', '-', '14,000.00']
    ];
    rows.forEach((row, index) => addTableRow(commands, row, columns, 501 - index * 25, index % 2 === 1));
    addSectionLabel(commands, 'Statement reconciliation', 235);
    addMetricCard(commands, 'Opening balance', 'RM 10,000.00', 42, 155, 120);
    addMetricCard(commands, 'Total credits', 'RM 10,000.00', 172, 155, 120);
    addMetricCard(commands, 'Total debits', 'RM 6,000.00', 302, 155, 120);
    addMetricCard(commands, 'Closing balance', 'RM 14,000.00', 432, 155, 121);
    addRect(commands, 42, 84, 511, 49, [0.97, 0.98, 0.95], olive, 0.7);
    addText(commands, 'RECONCILIATION CHECK', 56, 113, 7, 'bold', olive);
    addText(commands, 'Closing - opening: RM 4,000.00  |  Reported credits - debits: RM 4,000.00  |  Arithmetic agrees', 56, 94, 8, 'bold', ink);
    addText(commands, 'Bank Name: SYNTHETIC BANK', 42, 151, 1, 'regular', white);
    addText(commands, 'Opening Balance: RM 10,000.00', 42, 147, 1, 'regular', white);
    addText(commands, 'Total Credits: RM 10,000.00', 42, 143, 1, 'regular', white);
    addText(commands, 'Total Debits: RM 6,000.00', 42, 139, 1, 'regular', white);
    addText(commands, 'Closing Balance: RM 14,000.00', 42, 135, 1, 'regular', white);
    return [commands.join('\n')];
}

function buildSsmRegistration(): string[] {
    const commands: string[] = [];
    addPageChrome(commands, 'SSM / FORM-9', 'Company Registration Profile', 'Suruhanjaya Syarikat Malaysia - synthetic registry facsimile', 1, 1);
    addRect(commands, 42, 612, 511, 68, [0.96, 0.97, 0.93], olive, 0.8);
    addText(commands, 'REGISTERED ENTITY', 58, 657, 7.5, 'bold', olive);
    addText(commands, company, 58, 632, 17, 'bold', navy);
    addText(commands, 'Private company limited by shares', 58, 616, 8.5, 'regular', slate);
    addSectionLabel(commands, 'Registration particulars', 578);
    addInfoRow(commands, 'Registration Number:', 'SYNTHETIC-REG-001', 42, 542);
    addInfoRow(commands, 'Date of Incorporation:', '15 January 2020', 42, 512);
    addInfoRow(commands, 'Company Type:', 'SDN BHD', 42, 482);
    addInfoRow(commands, 'Business Address:', '1 Fictional Test Road, Kuala Lumpur', 42, 452);
    addInfoRow(commands, 'Paid-Up Capital:', 'RM 50,000.00', 42, 422);
    addSectionLabel(commands, 'Directors and officers', 380);
    addTableHeader(commands, ['No.', 'Name / identifier', 'Role', 'Status'], [54, 93, 430, 543], 349);
    addTableRow(commands, ['1', 'TEST DIRECTOR - TEST-ID-001', 'Director', 'Active'], [54, 93, 430, 543], 319, false);
    addText(commands, 'Directors:', 42, 305, 1, 'regular', white);
    addText(commands, '1. TEST DIRECTOR - NRIC: TEST-ID-001 - Role: Director', 42, 301, 1, 'regular', white);
    addSectionLabel(commands, 'Registry notice', 270);
    addRect(commands, 42, 170, 511, 72, [1, 0.97, 0.9], amber, 0.7);
    addText(commands, 'SYNTHETIC RECORD', 58, 218, 8, 'bold', [0.58, 0.31, 0.05]);
    addText(commands, 'This profile is a fictional test fixture generated for TraceLens product evaluation.', 58, 196, 9, 'regular', ink);
    addText(commands, 'It is not an SSM extract and must not be used for verification, filing or legal reliance.', 58, 180, 9, 'regular', ink);
    addText(commands, `Company Name: ${company}`, 42, 74, 1, 'regular', white);
    return [commands.join('\n')];
}

function buildFinancialPageOne(): string {
    const commands: string[] = [];
    addPageChrome(commands, 'AFS / FY-2025', 'Financial Statements', 'For the financial year ended 31 December 2025', 1, 2);
    addText(commands, company, 1, 839, 1, 'regular', navy);
    addRect(commands, 42, 627, 511, 54, [0.96, 0.97, 0.93], olive, 0.7);
    addText(commands, company, 58, 656, 13, 'bold', navy);
    addText(commands, 'Fictional audit fixture | Amounts in Malaysian Ringgit', 58, 638, 8, 'regular', slate);
    addSectionLabel(commands, 'Statement of profit or loss and cash flow', 594);
    const columns = [54, 455, 543];
    addTableHeader(commands, ['Financial line item', 'FY 2025', 'FY 2024'], columns, 563, 1);
    const rows = [
        ['Revenue', '120,000.00', '100,000.00'],
        ['Cost of Sales', '60,000.00', '50,000.00'],
        ['Gross Profit', '60,000.00', '50,000.00'],
        ['Operating Expenses', '30,000.00', '26,000.00'],
        ['EBIT', '30,000.00', '24,000.00'],
        ['Interest Expense', '3,000.00', '2,000.00'],
        ['Net Profit', '21,600.00', '17,600.00'],
        ['Cash from Operations', '28,000.00', '22,000.00']
    ];
    rows.forEach((row, index) => addTableRow(commands, row, columns, 533 - index * 30, index % 2 === 1, ['Gross Profit', 'EBIT', 'Net Profit'].includes(row[0]), 1));
    addSectionLabel(commands, 'Performance highlights', 276);
    addMetricCard(commands, 'Revenue growth', '+20.0%', 42, 184, 157);
    addMetricCard(commands, 'Net profit margin', '18.0%', 219, 184, 157);
    addMetricCard(commands, 'Interest coverage', '10.0x', 396, 184, 157);
    addRect(commands, 42, 91, 511, 68, soft, line, 0.7);
    addText(commands, 'BASIS OF PREPARATION', 58, 135, 7, 'bold', slate);
    addText(commands, 'Audited by: FICTIONAL TEST AUDITOR - no real audit performed.', 58, 113, 8.5, 'bold', ink);
    addText(commands, 'Comparative figures are included solely to exercise extraction, trend and ratio workflows.', 58, 97, 8.5, 'regular', slate);
    return commands.join('\n');
}

function buildFinancialPageTwo(): string {
    const commands: string[] = [];
    addPageChrome(commands, 'AFS / FY-2025', 'Financial Position', 'Comparative balances as at 31 December 2025', 2, 2);
    addRect(commands, 42, 627, 511, 54, [0.96, 0.97, 0.93], olive, 0.7);
    addText(commands, company, 58, 656, 13, 'bold', navy);
    addText(commands, 'Fictional audit fixture | Amounts in Malaysian Ringgit', 58, 638, 8, 'regular', slate);
    addSectionLabel(commands, 'Balance sheet', 594);
    const columns = [54, 455, 543];
    addTableHeader(commands, ['Financial line item', 'FY 2025', 'FY 2024'], columns, 563, 1);
    const rows = [
        ['Current Assets', '80,000.00', '65,000.00'],
        ['Non-Current Assets', '120,000.00', '115,000.00'],
        ['Total Assets', '200,000.00', '180,000.00'],
        ['Current Liabilities', '40,000.00', '35,000.00'],
        ['Non-Current Liabilities', '60,000.00', '55,000.00'],
        ['Total Liabilities', '100,000.00', '90,000.00'],
        ['Total Equity', '100,000.00', '90,000.00']
    ];
    rows.forEach((row, index) => addTableRow(commands, row, columns, 533 - index * 34, index % 2 === 1, row[0].startsWith('Total'), 1));
    addSectionLabel(commands, 'Calculated review indicators', 274);
    addMetricCard(commands, 'Current ratio', '2.00x', 42, 184, 157);
    addMetricCard(commands, 'Debt-to-equity', '1.00x', 219, 184, 157);
    addMetricCard(commands, 'Equity position', 'RM 100,000', 396, 184, 157);
    addRect(commands, 42, 91, 511, 68, soft, line, 0.7);
    addText(commands, 'REVIEW LIMITATION', 58, 135, 7, 'bold', slate);
    addText(commands, 'No verified annual principal and interest repayment schedule is included.', 58, 113, 8.5, 'bold', ink);
    addText(commands, 'Debt service coverage must remain unavailable until repayment evidence is supplied.', 58, 97, 8.5, 'regular', slate);
    return commands.join('\n');
}

function buildTaxReturn(): string[] {
    const commands: string[] = [];
    addPageChrome(commands, 'FORM C / YA-2025', 'Company Tax Return', 'Lembaga Hasil Dalam Negeri Malaysia - synthetic test facsimile', 1, 1);
    addRect(commands, 42, 616, 511, 66, [0.95, 0.97, 0.99], navyMuted, 0.8);
    addText(commands, 'BORANG C / FORM C', 58, 654, 15, 'bold', navy);
    addText(commands, 'RETURN FORM OF A COMPANY', 58, 632, 8.5, 'bold', slate);
    addSectionLabel(commands, 'Taxpayer particulars', 584);
    addInfoRow(commands, 'Company Name:', company, 42, 548);
    addInfoRow(commands, 'Tax Reference Number:', 'TEST-TAX-001', 42, 518);
    addInfoRow(commands, 'Year of Assessment:', '2025', 42, 488);
    addInfoRow(commands, 'Return Status:', 'ORIGINAL RETURN - SYNTHETIC SAMPLE', 42, 458);
    addSectionLabel(commands, 'Income computation summary', 416);
    const columns = [54, 543];
    addTableHeader(commands, ['Assessment item', 'Amount (RM)'], columns, 385, 1);
    const rows = [
        ['Gross Business Income:', 'RM 120,000.00'],
        ['Less: Salaries', '24,000.00'],
        ['Less: Rental', '12,000.00'],
        ['Less: Capital Allowance', '9,000.00'],
        ['Less: Other Deductions', '48,000.00'],
        ['Chargeable Income:', 'RM 27,000.00'],
        ['Tax Payable:', 'RM 5,400.00']
    ];
    rows.forEach((row, index) => addTableRow(commands, row, columns, 355 - index * 30, index % 2 === 1, index >= 5, 1));
    addRect(commands, 42, 88, 511, 49, [1, 0.96, 0.88], amber, 0.8);
    addText(commands, 'IMPORTANT NOTICE', 58, 116, 7, 'bold', [0.58, 0.31, 0.05]);
    addText(commands, 'Fixture amounts only. This is not a tax calculation, submission, acknowledgement or filing.', 58, 97, 8.5, 'bold', ink);
    return [commands.join('\n')];
}

const demoDocuments: DemoPdf[] = [
    { name: 'demo_bank_statement.pdf', pages: buildBankStatement },
    { name: 'demo_ssm_registration.pdf', pages: buildSsmRegistration },
    { name: 'demo_audited_financials.pdf', pages: () => [buildFinancialPageOne(), buildFinancialPageTwo()] },
    { name: 'demo_tax_return.pdf', pages: buildTaxReturn }
];

function createPdf(pages: string[]): ArrayBuffer {
    const objects: string[] = [];
    const pageIds = pages.map((_, index) => 5 + index * 2);
    objects[1] = '<< /Type /Catalog /Pages 2 0 R >>';
    objects[2] = `<< /Type /Pages /Kids [${pageIds.map((id) => `${id} 0 R`).join(' ')}] /Count ${pages.length} >>`;
    objects[3] = '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>';
    objects[4] = '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>';

    pages.forEach((commands, index) => {
        const pageId = pageIds[index];
        const contentId = pageId + 1;
        objects[pageId] = `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${pageWidth} ${pageHeight}] /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents ${contentId} 0 R >>`;
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
        [createPdf(document.pages())],
        document.name,
        { type: 'application/pdf', lastModified: 0 }
    ));
}
