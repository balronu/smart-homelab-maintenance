import { chromium, devices } from "playwright";
import http from "node:http";
import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const BROWSER_TIMEOUT = 15000;
const NAVIGATION_TIMEOUT = 15000;
const ACTION_TIMEOUT = 10000;
const TEST_TIMEOUT = 150000;
const cardSource = fs.readFileSync(path.join(root, "frontend/smart-homelab-maintenance-card.js"), "utf8");
if (/\b(?:scrollIntoView|scrollTo)\s*\(/.test(cardSource)) throw new Error("production card must not programmatically scroll");
const server = http.createServer((request, response) => {
  const requestPath = new URL(request.url, "http://127.0.0.1").pathname;
  const relative = requestPath === "/" ? "frontend/browser-harness.html" : requestPath.replace(/^\//, "");
  const file = path.resolve(root, relative);
  if (!file.startsWith(path.resolve(root) + path.sep) || !fs.existsSync(file)) { response.writeHead(404); response.end(); return; }
  const type = file.endsWith(".js") || file.endsWith(".mjs") ? "text/javascript" : "text/html";
  response.writeHead(200, { "Content-Type": type });
  fs.createReadStream(file).pipe(response);
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const port = server.address().port;

let browser;
let timedOut = false;
const watchdog = setTimeout(() => {
  timedOut = true;
  console.error(`browser matrix timeout after ${TEST_TIMEOUT}ms`);
  process.exitCode = 124;
  void (async () => {
    await browser?.close().catch(() => {});
    await new Promise((resolve) => server.close(resolve));
    process.exit(124);
  })();
}, TEST_TIMEOUT);
try {
  browser = await chromium.launch({ headless: true, timeout: BROWSER_TIMEOUT, executablePath: process.env.CHROMIUM_PATH || "/usr/bin/chromium" });
  const contexts = [
    { name: "iphone-dark", options: { ...devices["iPhone 13"], colorScheme: "dark" } },
    { name: "ipad-light", options: { ...devices["iPad (gen 7)"], colorScheme: "light" } },
    ...[768, 1024, 1440].map((width) => ({ name: `desktop-${width}`, options: { viewport: { width, height: 900 }, colorScheme: "light" } })),
  ];
  for (const { name, options } of contexts) {
    const context = await browser.newContext(options);
    const page = await context.newPage();
    page.setDefaultTimeout(ACTION_TIMEOUT);
    page.setDefaultNavigationTimeout(NAVIGATION_TIMEOUT);
    const browserErrors = [];
    const failedRequests = [];
    page.on("pageerror", (error) => browserErrors.push(error.message));
    page.on("requestfailed", (request) => failedRequests.push(`${request.url()}: ${request.failure()?.errorText || "failed"}`));
    await page.goto(`http://127.0.0.1:${port}/frontend/browser-harness.html`, { timeout: NAVIGATION_TIMEOUT, waitUntil: "load" });
    const sectionsSizing = await page.evaluate(() => {
      const card = document.createElement("smart-homelab-maintenance-card");
      return typeof card.getGridOptions === "function" ? card.getGridOptions() : null;
    });
    if (sectionsSizing?.rows !== "auto" || Object.hasOwn(sectionsSizing, "min_rows") || sectionsSizing?.columns !== "full") throw new Error(`${name} Sections sizing failed: ${JSON.stringify(sectionsSizing)}`);
    await page.waitForFunction(() => document.querySelector("#result")?.textContent.includes("connected"), null, { timeout: 10000 });
    const result = JSON.parse(await page.locator("#result").textContent());
    if (!result.connected || !result.hasContainer || !result.hasVm || !result.hasHost || !result.hasAvailableResources || !result.cardHasSize || !result.dryRunUi || !result.dryRunResponseShown || !result.installButtonDisabled || !result.dryRunMissingResponseShown || !result.dryRunServiceErrorShown || !result.dryRunTimeoutShown || !result.dryRunLocalizedAuthorizationShown || !result.unauthorizedSimulationUiSafe || !result.actionLayoutContractSafe || !result.vmExclusionEnglish || !result.vmExclusionGerman || !result.localizedEditor || !result.editorChanged || !result.editorPreservesFocusedDraft || !result.reopenedEditorSafe || !result.emptyCardSafe || !result.initialCardSafe || !result.unknownSafe || !result.unknownContainerSafe || !result.unknownVmMemorySafe || !result.guestAccessGermanSafe || !result.updateStatusLabelsSafe || !result.hostDetailsPreservedAfterUpdates || !result.languageEnglish || !result.languageGerman || !result.localeObjectSafe || !result.missingLanguageFallback || !result.hostOfflineWithoutAgentContradiction || !result.statusStatesSafe || result.errors.length || browserErrors.length || failedRequests.length || result.hasTextOverlap || result.hasHorizontalOverflow) throw new Error(`${name} failed: ${JSON.stringify({ result, browserErrors, failedRequests })}`);
    await page.screenshot({ path: `/tmp/card-${name}.png`, fullPage: true, timeout: ACTION_TIMEOUT });
    await page.goto(`http://127.0.0.1:${port}/frontend/ha-editor-harness.html`, { timeout: NAVIGATION_TIMEOUT, waitUntil: "load" });
    await page.waitForFunction(() => document.querySelector("#result")?.textContent.includes("pickerRegistered"), null, { timeout: 10000 });
    const haResult = JSON.parse(await page.locator("#result").textContent());
    if (!haResult.pickerRegistered || !haResult.editorVisible || !haResult.previewVisible || !haResult.savedAndReopened || !haResult.noHorizontalOverflow) throw new Error(`${name} HA editor harness failed: ${JSON.stringify(haResult)}`);
    await page.screenshot({ path: `/tmp/card-${name}-ha-editor.png`, fullPage: true, timeout: ACTION_TIMEOUT });
    await page.goto(`http://127.0.0.1:${port}/frontend/scroll-harness.html`, { timeout: NAVIGATION_TIMEOUT, waitUntil: "load" });
    await page.waitForFunction(() => document.querySelector("#result")?.textContent.includes("cardCount"), null, { timeout: 10000 });
    const scrollResult = JSON.parse(await page.locator("#result").textContent());
    if (!scrollResult.stableScroll || !scrollResult.stableDom || !scrollResult.stableOrder || scrollResult.gridMutations !== 0 || scrollResult.dashboardMutations !== 0 || !scrollResult.focusStable || !scrollResult.hostCardsStable || !scrollResult.independentDetails || !scrollResult.noHorizontalOverflow || scrollResult.cardCount !== 3) throw new Error(`${name} scroll harness failed: ${JSON.stringify(scrollResult)}`);
    await page.screenshot({ path: `/tmp/card-${name}-scroll.png`, fullPage: true, timeout: ACTION_TIMEOUT });
    // Reachability test with a long container list. Layouts here are simulated,
    // not Home Assistant's real Sections/Masonry layout implementation.
    for (const count of [0, 1, 10, 20, 50]) for (const layout of ["sections", "masonry"]) {
      await page.goto(`http://127.0.0.1:${port}/frontend/long-card-scroll-harness.html?count=${count}`, { timeout: NAVIGATION_TIMEOUT, waitUntil: "load" });
      await page.waitForFunction(() => window.__FIXTURE_READY__ === true, null, { timeout: ACTION_TIMEOUT });
      const reachability = await page.evaluate((layout) => {
        document.querySelector("#dashboard").className = layout;
        const card = document.querySelector("smart-homelab-maintenance-card");
        const last = [...card.shadowRoot.querySelectorAll(".container-grid .item")].at(-1);
        const sentinel = document.querySelector("#after");
        const fullHeight = document.documentElement.scrollHeight;
        window.scrollTo(0, fullHeight);
        return { expectedCount: Number(new URLSearchParams(location.search).get("count")), count: card.shadowRoot.querySelectorAll(".container-grid .item").length,
          lastText: last?.textContent || "", lastBottom: last?.getBoundingClientRect().bottom,
          sentinelBottom: sentinel.getBoundingClientRect().bottom,
          viewportHeight: innerHeight, scrollY: window.scrollY,
          fullHeight, maxScroll: fullHeight - innerHeight };
      }, layout);
      if (reachability.count !== reachability.expectedCount || (reachability.expectedCount > 0 && !reachability.lastText.includes(String(99 + reachability.expectedCount))) ||
          reachability.lastBottom > reachability.viewportHeight + 2 ||
          reachability.sentinelBottom > reachability.viewportHeight + 2 ||
          reachability.scrollY < reachability.maxScroll - 2) {
        throw new Error(`${name} ${layout} long-card scroll reachability failed: ${JSON.stringify(reachability)}`);
      }
      await page.screenshot({ path: `/tmp/card-${name}-long-${layout}.png`, fullPage: true, timeout: ACTION_TIMEOUT });
    }
    // Negative control: a clipping ancestor must be detected even when the
    // document scrolls to its maximum. This reproduces the symptom, not HA internals.
    await page.goto(`http://127.0.0.1:${port}/frontend/long-card-scroll-harness.html`, { timeout: NAVIGATION_TIMEOUT, waitUntil: "load" });
    await page.waitForFunction(() => window.__FIXTURE_READY__ === true, null, { timeout: ACTION_TIMEOUT });
    const clipping = await page.evaluate(() => {
      const dashboard = document.querySelector("#dashboard");
      dashboard.style.height = "400px";
      dashboard.style.overflow = "hidden";
      const card = document.querySelector("smart-homelab-maintenance-card");
      const last = [...card.shadowRoot.querySelectorAll(".container-grid .item")].at(-1);
      const parent = card.parentElement;
      const style = getComputedStyle(parent);
      const parentBox = parent.getBoundingClientRect();
      const lastBox = last.getBoundingClientRect();
      return { overflowY: style.overflowY, parentBottom: parentBox.bottom,
        lastBottom: lastBox.bottom, clipped: lastBox.bottom > parentBox.bottom + 2 };
    });
    if (clipping.overflowY !== "hidden" || !clipping.clipped) {
      throw new Error(`${name} clipping negative control failed: ${JSON.stringify(clipping)}`);
    }
    await page.goto(`http://127.0.0.1:${port}/frontend/sections-scroll-regression.html`, { timeout: NAVIGATION_TIMEOUT, waitUntil: "load" });
    await page.waitForFunction(() => document.querySelector("#result")?.textContent.includes("legacyReproducesClip"), null, { timeout: 10000 });
    const sectionsRegression = JSON.parse(await page.locator("#result").textContent());
    if (!sectionsRegression.legacyReproducesClip || !sectionsRegression.fixedReachable || sectionsRegression.cardCount !== 2 || !sectionsRegression.lastText.includes("112")) {
      throw new Error(`${name} Sections stale-height regression failed: ${JSON.stringify(sectionsRegression)}`);
    }
    await page.close();
    await context.close();
  }
} finally {
  clearTimeout(watchdog);
  await browser?.close();
  await new Promise((resolve) => server.close(resolve));
}
if (!timedOut) console.log("browser matrix passed");
