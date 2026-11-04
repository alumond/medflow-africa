// Optional documentation tool. Install Playwright separately from the Python app.
import { mkdir, writeFile, stat } from 'node:fs/promises';
import { resolve } from 'node:path';
const { chromium } = await import(process.env.MEDFLOW_PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.MEDFLOW_BASE_URL || 'https://medflow-africa.vercel.app';
const output = resolve(process.env.MEDFLOW_SCREENSHOT_DIR || 'docs/screenshots');
await mkdir(output, { recursive: true });
const browser = await chromium.launch({
  headless: true,
  ...(process.env.MEDFLOW_BROWSER_PATH ? { executablePath: process.env.MEDFLOW_BROWSER_PATH } : {}),
});
const context = await browser.newContext({
  viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 1,
  locale: 'en-GB', reducedMotion: 'reduce',
});
const page = await context.newPage();
page.setDefaultTimeout(60000);
const errors = [];
page.on('pageerror', error => errors.push(error.message));
const captures = [];
async function save(file, title, fullPage = true) {
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: resolve(output, file), fullPage, animations: 'disabled' });
  captures.push({ file, title, url: page.url(), bytes: (await stat(resolve(output, file))).size });
  console.log(`Saved ${file}`);
}
async function go(route, heading) {
  await page.goto(`${base}/?capture=20261104-${route}#${route}`, { waitUntil: 'domcontentloaded' });
  await page.getByRole('heading', { name: heading, exact: true, level: 1 }).waitFor();
}
async function closeDialogs() {
  while (await page.locator('dialog[open]').count()) {
    const count = await page.locator('dialog[open]').count();
    await page.keyboard.press('Escape');
    await page.waitForFunction(n => document.querySelectorAll('dialog[open]').length < n, count);
  }
}
try {
  await go('overview', 'District overview.');
  await save('01-district-overview.png', 'District overview');

  await go('risks', 'Risk explorer.');
  await save('02-risk-explorer.png', 'Risk explorer — first screen', false);
  await save('02b-risk-explorer-full.png', 'Risk explorer — complete table');
  await page.getByRole('button', { name: 'Investigate Oke Rural Clinic — Amoxicillin 500 mg', exact: true }).click();
  await page.locator('#detailDialog[open]').waitFor();
  await save('03-risk-detail.png', 'Individual stock risk and model factors', false);
  await page.getByRole('button', { name: /Explain this risk/ }).click();
  await page.locator('#assistanceContent .source-chip').first().waitFor();
  await save('11-integrated-explanation.png', 'Contextual explanation with source records', false);
  await closeDialogs();

  await go('planner', 'Redistribution planner.');
  await save('04-redistribution-planner.png', 'Safe redistribution options');
  await page.getByRole('button', { name: 'Review proposal', exact: true }).first().click();
  await page.getByRole('heading', { name: 'Review the proposal.', exact: true }).waitFor();
  await save('05-transfer-review.png', 'Human review and safety constraints', false);
  await closeDialogs();

  await go('quality', 'Data quality.');
  await save('06-data-quality.png', 'Data quality and rejected records');
  await page.getByRole('button', { name: 'Import data', exact: true }).click();
  await page.getByRole('heading', { name: 'Start with the evidence.', exact: true }).waitFor();
  await save('07-data-import.png', 'Four-file data import', false);
  await closeDialogs();

  await go('report', 'Supply brief.');
  await page.getByLabel('Narrative approach', { exact: true }).selectOption('deterministic');
  const executive = await page.locator('.report-sheet').innerText();
  if (/Training is at|Stock officers trained|Facilities with physical stock verification/.test(executive)) {
    throw new Error('Planning examples leaked into the operational executive preview');
  }
  await save('08-supply-brief.png', 'Operational executive preview');
  await page.getByRole('button', { name: 'Readiness & resources', exact: true }).click();
  await page.getByText('These are example project-planning records.', { exact: false }).waitFor();
  await save('12-project-resources.png', 'Labelled example project resources');
  await page.getByRole('button', { name: 'Action register', exact: true }).click();
  await page.getByRole('heading', { name: 'Name the next step.', exact: true }).waitFor();
  await save('13-action-register.png', 'Actions, owners and deadlines');
  await page.getByRole('button', { name: 'Escalation email', exact: true }).click();
  await page.getByRole('button', { name: 'Generate escalation draft', exact: true }).click();
  await page.locator('.email-subject').waitFor();
  await save('10-escalation-draft.png', 'Separate escalation draft — no email sent');
  await page.getByRole('button', { name: /Preview full report/ }).click();
  await page.frameLocator('#reportFrame').locator('h2').first().waitFor();
  await save('09-report-preview.png', 'Full report preview and export controls', false);
  await closeDialogs();

  await page.goto(`${base}/api/reports/action-report?window=14`, { waitUntil: 'domcontentloaded' });
  await page.locator('section').last().waitFor();
  if (await page.locator('section').count() !== 13) throw new Error('Incomplete report');
  if (/Stock officers trained|physical stock verification|training places/i.test(await page.locator('body').innerText())) {
    throw new Error('Removed planning achievements reappeared in report output');
  }
  await save('09b-complete-report.png', 'All thirteen report sections');

  await go('ai', 'Model performance.');
  await page.getByRole('button', { name: 'Load monitoring evidence', exact: true }).click();
  await page.getByRole('heading', { name: 'The validation decision.', exact: true }).waitFor();
  await save('14-model-performance.png', 'Model evaluation, drift and review feedback');

  await page.setViewportSize({ width: 390, height: 844 });
  await go('overview', 'District overview.');
  await save('15-mobile-overview.png', 'Mobile district overview');

  if (errors.length) throw new Error(`Browser errors: ${errors.join('; ')}`);
  await writeFile(resolve(output, 'manifest.json'), JSON.stringify({
    captured_at: new Date().toISOString(), website: base, method: 'Playwright',
    desktop_viewport: { width: 1600, height: 1000 },
    note: 'Fresh isolated browser workspace with bundled example records. No stock decisions or emails submitted.',
    captures,
  }, null, 2) + '\n');
  console.log(`Completed ${captures.length} screenshots without browser errors.`);
} finally {
  await browser.close();
}
