/*
 * render.js — turn visuals.html into STRATA-demo.mp4
 *
 *   node deck/video/render.js
 *
 * Needs playwright and ffmpeg. Takes about three minutes: it plays the reel
 * once in real time while recording, then corrects and encodes.
 *
 * WHY THE TIMING CORRECTION EXISTS
 *
 * Chromium records video by screencasting frames to an encoder. On a machine
 * with no GPU that encoder falls behind, and the timestamps it writes stretch —
 * the animation itself runs on schedule in real seconds, but the resulting file
 * plays roughly 10% slow. So we measure how long the reel actually took by the
 * clock, compare it with the duration the encoder claims, and rescale the
 * presentation timestamps by that ratio. Every beat then lands within about a
 * second of the script's own timings.
 *
 * Do not "fix" this by speeding the animation up instead. The animation is
 * right; the container's timestamps are wrong.
 */

const { chromium } = require('playwright');
const { execFileSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const HERE = __dirname;
const PAGE = 'file://' + path.join(HERE, 'visuals.html');
const OUT = path.join(HERE, 'STRATA-demo.mp4');
const HOLD_MS = 3200;          // how long to sit on the end card
const GIVE_UP_MS = 200000;

(async () => {
  if (!fs.existsSync(path.join(HERE, 'visuals.html'))) {
    console.error('visuals.html not found — run build_visuals.py first');
    process.exit(1);
  }
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'strata-render-'));

  const browser = await chromium.launch({
    args: ['--force-device-scale-factor=1', '--hide-scrollbars',
           '--disable-background-timer-throttling',
           '--disable-backgrounding-occluded-windows',
           '--disable-renderer-backgrounding'],
  });
  const ctx = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: 1,
    recordVideo: { dir: tmp, size: { width: 1920, height: 1080 } },
  });
  const page = await ctx.newPage();

  await page.goto(PAGE);
  const t0 = Date.now();                       // the reel autostarts on load
  process.stdout.write('recording');
  for (;;) {
    await page.waitForTimeout(500);
    // `i` is a top-level `let`, so it is lexical — not on window
    const cue = await page.evaluate(() => i);
    if (cue >= 22) break;
    if (Date.now() - t0 > GIVE_UP_MS) { console.log('\ngave up waiting for the final cue'); break; }
    if ((Date.now() - t0) % 5000 < 520) process.stdout.write('.');
  }
  await page.waitForTimeout(HOLD_MS);
  const realSecs = (Date.now() - t0 + HOLD_MS) / 1000;
  await ctx.close();
  await browser.close();
  console.log(`\nreel played in ${realSecs.toFixed(1)}s of real time`);

  const webm = path.join(tmp, fs.readdirSync(tmp).find(f => f.endsWith('.webm')));
  const claimed = parseFloat(execFileSync('ffprobe',
    ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', webm])
    .toString().trim());
  const correction = realSecs / claimed;
  console.log(`encoder claimed ${claimed.toFixed(2)}s → correcting by ${correction.toFixed(5)}`);

  execFileSync('ffmpeg', [
    '-v', 'error', '-i', webm,
    '-vf', `setpts=${correction.toFixed(5)}*PTS,fps=25`,
    '-an', '-c:v', 'libx264', '-crf', '19', '-preset', 'slow',
    '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
    '-t', realSecs.toFixed(2), OUT, '-y',
  ], { stdio: 'inherit' });

  fs.rmSync(tmp, { recursive: true, force: true });
  const mb = (fs.statSync(OUT).size / 1e6).toFixed(1);
  console.log(`wrote ${OUT}  (${mb} MB, ${realSecs.toFixed(0)}s, 1920x1080, silent)`);
})();
