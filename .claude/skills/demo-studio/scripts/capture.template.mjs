// Playwright screen-capture template for demo-studio.
// COPY this file per app (e.g. to the session scratchpad), fill in APP_URL,
// VIEWPORT, and one entry in ACTIONS per script segment, then run:
//   node capture.mjs <timeline.json> <out_dir>
// The app must already be running at APP_URL. Each segment's action runs
// while that segment's narration plays; the runner pads to the segment's
// measured duration so footage and voiceover stay in sync at assembly time.
import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';

const APP_URL = 'http://localhost:8000';
const VIEWPORT = { width: 1600, height: 900 };

// One async fn per segment id. Keep motions slow and deliberate — this is
// footage, not a test. Useful moves: page.mouse.move (glide), smoothScroll,
// hover to trigger tooltips, click to change tabs, pause on the money shot.
const ACTIONS = {
  // intro: async (page) => { await page.goto(APP_URL); },
  // features: async (page) => { await page.click('text=Cost center'); await smoothScroll(page, 600); },
};

async function smoothScroll(page, px, steps = 30) {
  for (let i = 0; i < steps; i++) {
    await page.mouse.wheel(0, px / steps);
    await page.waitForTimeout(40);
  }
}

const [timelinePath, outDir] = process.argv.slice(2);
const timeline = JSON.parse(fs.readFileSync(timelinePath, 'utf8'));
fs.mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: VIEWPORT,
  recordVideo: { dir: outDir, size: VIEWPORT },
});
const page = await context.newPage();
const recStart = Date.now(); // recording begins with the page
await page.goto(APP_URL, { waitUntil: 'networkidle' });
await page.waitForTimeout(500); // settle before the first beat
// footage before this point is page load — assemble.sh trims it via lead.json
fs.writeFileSync(
  path.join(outDir, 'lead.json'),
  JSON.stringify({ leadSeconds: (Date.now() - recStart) / 1000 })
);

for (const seg of timeline.segments) {
  const t0 = Date.now();
  const action = ACTIONS[seg.id];
  if (action) {
    await action(page);
  } else {
    console.warn(`no action for segment "${seg.id}" — holding still`);
  }
  // pad to narration length (+ inter-segment gap) so video matches audio
  const elapsed = (Date.now() - t0) / 1000;
  const target = seg.duration + timeline.gap;
  if (elapsed < target) await page.waitForTimeout((target - elapsed) * 1000);
  else console.warn(`segment "${seg.id}" action ran ${elapsed.toFixed(1)}s, longer than its ${target.toFixed(1)}s slot — re-time it`);
  console.log(`segment ${seg.id} done`);
}

await context.close(); // flushes the video
const video = fs.readdirSync(outDir).find((f) => f.endsWith('.webm'));
fs.renameSync(path.join(outDir, video), path.join(outDir, 'capture.webm'));
await browser.close();
console.log(`wrote ${path.join(outDir, 'capture.webm')}`);
