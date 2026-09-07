/* P3-5 观感验收截图：sheet 74 全图 + 放大细节 + 选中高亮 */
import { chromium } from "playwright-core";
const CHROME = "C:/Users/Solomon/AppData/Local/ms-playwright/chromium-1223/chrome-win64/chrome.exe";
const OUT = "artifacts/phase3_visual";
import { mkdirSync } from "fs";

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: CHROME });
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
await page.goto("http://localhost:5173/", { waitUntil: "domcontentloaded" });
await page.waitForSelector("canvas", { timeout: 15000 });
await new Promise(r => setTimeout(r, 3000));

// 切到 sheet 74（4万实体）
const sel = page.locator("select").first();
const opts = await sel.locator("option").allTextContents();
const hit = opts.findIndex((o) => o.startsWith("#74"));
if (hit < 0) throw new Error("sheet74 missing");
await sel.selectOption({ index: hit });
await new Promise(r => setTimeout(r, 2500));

// 1) 全图概览（LOD0）
await page.screenshot({ path: `${OUT}/s74_overview.png` });

// 2) 滚轮放大两级（细节 LOD1）
const canvas = page.locator("canvas");
const box = await canvas.boundingBox();
const cx = box.x + box.width / 2, cy = box.y + box.height / 2;
for (let i = 0; i < 6; i++) {
  await page.mouse.move(cx, cy);
  await page.mouse.wheel(0, -240);
  await new Promise(r => setTimeout(r, 350));
}
await new Promise(r => setTimeout(r, 1500));
await page.screenshot({ path: `${OUT}/s74_zoom_lod1.png` });

// 状态栏 info
const info = await page.locator("div[style*=bottom]").first().textContent().catch(() => "");
console.log("info:", info?.trim());
await browser.close();
console.log("screenshots:", OUT);