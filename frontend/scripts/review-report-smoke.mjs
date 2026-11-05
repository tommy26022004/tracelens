import { chromium } from 'playwright';

const api = process.env.TRACELENS_API_URL ?? 'http://localhost:8000';
const site = process.env.TRACELENS_URL ?? 'http://localhost:5173';
const history = await (await fetch(`${api}/api/history?limit=20`)).json();
const record = history.items.find((item) => item.category === 'analysis' && item.status === 'completed');
if (!record) throw new Error('No completed saved analysis run is available');

const browser = await chromium.launch({ channel: 'chrome', headless: true });
try {
    const page = await browser.newPage();
    await page.goto(`${site}/?saved=${encodeURIComponent(record.id)}`, { waitUntil: 'networkidle' });
    await page.getByRole('heading', { name: 'Credit assessment dashboard' }).waitFor();
    await page.getByRole('heading', { name: 'Document readiness advisor' }).waitFor();
    const popupPromise = page.waitForEvent('popup');
    await page.getByRole('button', { name: 'Print / save review report' }).click();
    const report = await popupPromise;
    await report.getByRole('heading', { name: 'TraceLens — Human review report' }).waitFor();
    await report.getByText('Decision support only.').first().waitFor();
    const pdf = await report.pdf({ format: 'A4', printBackground: true });
    if (!pdf.subarray(0, 4).equals(Buffer.from('%PDF'))) throw new Error('PDF export is invalid');
    process.stdout.write(JSON.stringify({
        run_id: record.id,
        advisor_actions: await page.locator('[aria-labelledby="readiness-title"] li').count(),
        pdf_bytes: pdf.length,
        source_index: await report.getByRole('heading', { name: 'Source index' }).count()
    }) + '\n');
} finally {
    await browser.close();
}
