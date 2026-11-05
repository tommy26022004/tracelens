import { chromium } from 'playwright';

const baseUrl = process.env.TRACELENS_URL ?? 'http://localhost:5173';
const runs = Number(process.env.TRACELENS_E2E_RUNS ?? '3');
const browser = await chromium.launch({ headless: true, channel: 'chrome' });
const outcomes = [];

try {
    for (let index = 0; index < runs; index += 1) {
        const context = await browser.newContext();
        const page = await context.newPage();
        page.on('pageerror', (error) => process.stderr.write(`Browser error: ${error.message}\n`));
        const started = Date.now();
        try {
            await page.goto(baseUrl, { waitUntil: 'networkidle' });
            const closeTour = page.getByRole('button', { name: 'Close product tour' });
            if (await closeTour.isVisible()) await closeTour.click();
            await page.getByRole('button', { name: 'Try sample package' }).click();
            await page.getByText('demo_bank_statement.pdf').first().waitFor();
            await page.getByRole('button', { name: 'Analyse package' }).click();
            await page.getByRole('heading', { name: 'Credit assessment dashboard' }).waitFor({ timeout: 600_000 });
            await page.getByText('Human verification required').first().waitFor();
            await page.locator('[data-view="evidence"]').click();
            await page.getByText('Sources cited or retrieved').first().waitFor();
            await page.locator('details[open] ul button').first().click();
            await page.getByText('SOURCE CITATION').waitFor();
            await page.getByRole('link', { name: /Open original PDF/ }).waitFor();
            outcomes.push({ run: index + 1, passed: true, seconds: (Date.now() - started) / 1000 });
        } catch (error) {
            outcomes.push({ run: index + 1, passed: false, error: String(error) });
            throw error;
        } finally {
            await context.close();
        }
    }
} finally {
    await browser.close();
    process.stdout.write(`${JSON.stringify(outcomes, null, 2)}\n`);
}
