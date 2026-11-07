import { chromium, devices } from "playwright";
import http from "node:http";
import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const cardSource = fs.readFileSync(path.join(root, "frontend/smart-homelab-maintenance-card.js"), "utf8");
if (/\b(?:scrollIntoView|scrollTo)\s*\(/.test(cardSource)) throw new Error("production card must not programmatically scroll");
const server = http.createServer((request, response) => {
  const relative = request.url === "/" ? "frontend/browser-harness.html" : request.url.replace(/^\//, "");
  const file = path.resolve(root, relative);
  if (!file.startsWith(path.resolve(root) + path.sep) || !fs.existsSync(file)) { response.writeHead(404); response.end(); return; }
  const type = file.endsWith(".js") || file.endsWith(".mjs") ? "text/javascript" : "text/html";
  response.writeHead(200, { "Content-Type": type });
  fs.createReadStream(file).pipe(response);
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const port = server.address().port;

const browser = await chromium.launch({ headless: true });
try {
  const contexts = [
    { name: "iphone-dark", options: { ...devices["iPhone 13"], colorScheme: "dark" } },
    { name: "ipad-light", options: { ...devices["iPad (gen 7)"], colorScheme: "light" } },
    ...[768, 1024, 1440].map((width) => ({ name: `desktop-${width}`, options: { viewport: { width, height: 900 }, colorScheme: "light" } })),
  ];
  for (const { name, options } of contexts) {
    const context = await browser.newContext(options);
    const page = await context.newPage();
    const browserErrors = [];
    const failedRequests = [];
    page.on("pageerror", (error) => browserErrors.push(error.message));
    page.on("requestfailed", (request) => failedRequests.push(`${request.url()}: ${request.failure()?.errorText || "failed"}`));
    await page.goto(`http://127.0.0.1:${port}/frontend/browser-harness.html`);
    const sectionsSizing = await page.evaluate(() => {
      const card = document.createElement("smart-homelab-maintenance-card");
      return typeof card.getGridOptions === "function" ? card.getGridOptions() : null;
    });
    if (sectionsSizing?.rows !== "auto" || sectionsSizing?.min_rows !== 6 || sectionsSizing?.columns !== "full") throw new Error(`${name} Sections sizing failed: ${JSON.stringify(sectionsSizing)}`);
    await page.waitForFunction(() => document.querySelector("#result")?.textContent.includes("connected"), null, { timeout: 10000 });
    const result = JSON.parse(await page.locator("#result").textContent());
    if (!result.connected || !result.hasContainer || !result.hasVm || !result.hasHost || !result.hasAvailableResources || !result.cardHasSize || !result.localizedEditor || !result.editorChanged || !result.editorPreservesFocusedDraft || !result.reopenedEditorSafe || !result.emptyCardSafe || !result.initialCardSafe || !result.unknownSafe || !result.unknownContainerSafe || !result.hostDetailsPreservedAfterUpdates || !result.languageEnglish || !result.languageGerman || !result.localeObjectSafe || !result.missingLanguageFallback || !result.hostOfflineWithoutAgentContradiction || !result.statusStatesSafe || result.errors.length || browserErrors.length || failedRequests.length || result.hasTextOverlap || result.hasHorizontalOverflow) throw new Error(`${name} failed: ${JSON.stringify({ result, browserErrors, failedRequests })}`);
    await page.screenshot({ path: `/tmp/card-${name}.png`, fullPage: true });
    await page.goto(`http://127.0.0.1:${port}/frontend/ha-editor-harness.html`);
    await page.waitForFunction(() => document.querySelector("#result")?.textContent.includes("pickerRegistered"), null, { timeout: 10000 });
    const haResult = JSON.parse(await page.locator("#result").textContent());
    if (!haResult.pickerRegistered || !haResult.editorVisible || !haResult.previewVisible || !haResult.savedAndReopened || !haResult.noHorizontalOverflow) throw new Error(`${name} HA editor harness failed: ${JSON.stringify(haResult)}`);
    await page.screenshot({ path: `/tmp/card-${name}-ha-editor.png`, fullPage: true });
    await page.goto(`http://127.0.0.1:${port}/frontend/scroll-harness.html`);
    await page.waitForFunction(() => document.querySelector("#result")?.textContent.includes("cardCount"), null, { timeout: 10000 });
    const scrollResult = JSON.parse(await page.locator("#result").textContent());
    if (!scrollResult.stableScroll || !scrollResult.stableDom || !scrollResult.stableOrder || scrollResult.gridMutations !== 0 || scrollResult.dashboardMutations !== 0 || !scrollResult.focusStable || !scrollResult.hostCardsStable || !scrollResult.independentDetails || !scrollResult.noHorizontalOverflow || scrollResult.cardCount !== 3) throw new Error(`${name} scroll harness failed: ${JSON.stringify(scrollResult)}`);
    await page.screenshot({ path: `/tmp/card-${name}-scroll.png`, fullPage: true });
    await page.close();
    await context.close();
  }
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}
console.log("browser matrix passed");
