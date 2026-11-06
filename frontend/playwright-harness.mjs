import { chromium } from "playwright";
import http from "node:http";
import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
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
  for (const width of [390, 768, 1024, 1440]) {
    const page = await browser.newPage({ viewport: { width, height: 900 }, colorScheme: "light" });
    await page.goto(`http://127.0.0.1:${port}/frontend/browser-harness.html`);
    await page.waitForFunction(() => document.querySelector("#result")?.textContent.includes("connected"), null, { timeout: 10000 });
    const result = JSON.parse(await page.locator("#result").textContent());
    if (!result.connected || !result.hasContainer || !result.hasVm || !result.hasHost || !result.editorChanged || result.hasHorizontalOverflow) throw new Error(`light ${width}px failed`);
    await page.screenshot({ path: `/tmp/card-${width}-light.png` });
    await page.emulateMedia({ colorScheme: "dark" });
    if (!(await page.locator(".card").count()) || !(await page.locator("#editor").count())) throw new Error(`dark ${width}px failed`);
    await page.screenshot({ path: `/tmp/card-${width}-dark.png` });
    await page.close();
  }
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}
console.log("browser matrix passed");
