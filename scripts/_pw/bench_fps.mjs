/* P3-4 前端平移 fps 实测（Playwright 驱动，Chromium）
 *
 * 场景：
 *   1. 加载 sheet 74（4万）/ sheet 75（7.9万）
 *   2. 拖拽平移 60 次 → rAF 计数算 fps（注入一次循环，结束时读值）
 *   3. Performance API 统计 /api/cad/viewport 请求耗时
 */
import { chromium } from "playwright-core";

const BASE = "http://localhost:5173";
const SHEETS = [74, 75];
const CHROME = process.env.CHROME_PATH || "C:/Users/Solomon/AppData/Local/ms-playwright/chromium-1223/chrome-win64/chrome.exe";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function bench(browser, sheetId) {
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  await page.goto(BASE + "/", { waitUntil: "domcontentloaded" });
  await page.waitForSelector("canvas", { timeout: 15000 });
  await sleep(2500);

  // 切图到目标 sheet
  const sel = page.locator("select").first();
  const opts = await sel.locator("option").allTextContents();
  const hit = opts.findIndex((o) => o.startsWith(`#${sheetId}`));
  if (hit < 0) throw new Error(`sheet ${sheetId} not in select`);
  await sel.selectOption({ index: hit });
  await sleep(1500);
  await page.evaluate(() => window.scrollTo(0, 0));

  const box = await page.locator("canvas").boundingBox();
  if (!box) throw new Error("canvas boundingBox null");
  const cx = box.x + box.width / 2;
  const cy = box.y + box.height / 2;

  // 预热一轮拖动
  await page.mouse.move(cx, cy);
  await page.mouse.down();
  await page.mouse.move(cx + 30, cy + 20, { steps: 3 });
  await page.mouse.up();
  await sleep(800);

  // 注入 rAF 计数器（拖拽期间 page 一直活跃）
  await page.evaluate(() => {
    window.__rafCount = 0;
    const tick = () => { window.__rafCount += 1; requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
  });
  const tStart = Date.now();
  const N = 60;
  for (let i = 0; i < N; i++) {
    const dx = Math.sin(i / 6) * 120;
    const dy = Math.cos(i / 7) * 80;
    await page.mouse.move(cx, cy);
    await page.mouse.down();
    await page.mouse.move(cx + dx, cy + dy, { steps: 4 });
    await page.mouse.up();
    await sleep(45);
  }
  const elapsed = (Date.now() - tStart) / 1000;
  const rafCount = await page.evaluate(() => window.__rafCount);
  const fps = rafCount / elapsed;

  const timings = await page.evaluate(() =>
    performance.getEntriesByType("resource")
      .filter((e) => e.name.includes("/api/cad/viewport"))
      .map((e) => e.duration)
  );
  const info = await page.locator("div[style*=bottom]").first().textContent().catch(() => "");
  await page.close();

  const maxApi = timings.length ? Math.max(...timings) : 0;
  const avgApi = timings.length ? timings.reduce((s, t) => s + t, 0) / timings.length : 0;
  console.log(`SHEET ${sheetId}: fps=${fps.toFixed(1)} (raf=${rafCount} in ${elapsed.toFixed(1)}s) viewport_req=${timings.length} max_api_ms=${maxApi.toFixed(0)} avg_api_ms=${avgApi.toFixed(0)} info="${info?.trim()}"`);
}

const browser = await chromium.launch({ executablePath: CHROME });
for (const sid of SHEETS) {
  try {
    await bench(browser, sid);
  } catch (e) {
    console.log(`SHEET ${sid}: ERROR ${e.message.split("\n")[0]}`);
  }
}
await browser.close();