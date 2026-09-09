/*
 * render.js — turn logo.html into STRATA-logo.mp4
 *
 *   node deck/logo/render.js
 *
 * Needs playwright and ffmpeg. Takes about a minute.
 *
 * Same timestamp correction as the video reel: Chromium screencasts frames
 * to an encoder that falls behind on a machine with no GPU and writes
 * stretched timestamps, so the file plays slower than the animation
 * actually ran. We measure the real elapsed time, compare it with the
 * duration the encoder claims, and rescale presentation timestamps by that
 * ratio. The animation is right; the container's timing is not.
 */

const { chromium } = require('playwright');
const { execFileSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const HERE = __dirname;
const PAGE = 'file://' + path.join(HERE, 'logo.html');
const OUT  = path.join(HERE, 'STRATA-logo.mp4');
const CUT  = 9.6;                    // one cycle, trimmed before it loops

(async () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'strata-logo-'));
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

  // restart the clock now that the page has painted, so the recording
  // begins on frame one of the animation rather than part-way in
  await page.evaluate(() => { start = null; });
  const t0 = Date.now();
  await page.waitForTimeout(10600);
  const realSecs = (Date.now() - t0) / 1000;

  await ctx.close();
  await browser.close();

  const webm = path.join(tmp, fs.readdirSync(tmp).find(f => f.endsWith('.webm')));
  const claimed = parseFloat(execFileSync('ffprobe',
    ['-v','error','-show_entries','format=duration','-of','csv=p=0', webm])
    .toString().trim());
  const correction = realSecs / claimed;
  console.log(`played ${realSecs.toFixed(1)}s · encoder claimed ${claimed.toFixed(2)}s ` +
              `· correcting by ${correction.toFixed(5)}`);

  execFileSync('ffmpeg', [
    '-v','error','-i', webm,
    '-vf', `setpts=${correction.toFixed(5)}*PTS,fps=30`,
    '-an','-c:v','libx264','-crf','18','-preset','slow',
    '-pix_fmt','yuv420p','-movflags','+faststart',
    '-t', String(CUT), OUT, '-y',
  ], { stdio: 'inherit' });

  fs.rmSync(tmp, { recursive: true, force: true });
  console.log(`wrote ${OUT}  (${(fs.statSync(OUT).size/1e6).toFixed(1)} MB, ${CUT}s, 1920x1080, silent)`);
})();
