import assert from 'node:assert/strict'
import { mkdir, mkdtemp, readFile, readdir, rm, stat, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { test } from 'node:test'
import { chromium } from 'playwright-core'
import { executable, freePort, studio, visible } from './studio.mjs'

const media = process.env.KOMA_TEST_MEDIA_DIR ? resolve(process.env.KOMA_TEST_MEDIA_DIR) : null
const fps = 30, frames = 294
const args = JSON.parse(process.env.KOMA_CHROMIUM_ARGS || '[]')

async function withPage(run) {
  assert.ok(executable, 'Set KOMA_CHROMIUM_EXECUTABLE to an installed Chromium, Chrome or Edge executable.')
  const root = await mkdtemp(join(tmpdir(), 'Koma motion test '))
  const workspace = join(root, 'Local films বাগান')
  const port = await freePort()
  const origin = `http://127.0.0.1:${port}`
  let close, browser
  try {
    close = await studio(workspace, port)
    browser = await chromium.launch({ executablePath: executable, headless: true, args })
    const page = await browser.newPage({ baseURL: origin, viewport: { width: 1440, height: 900 }, acceptDownloads: true, serviceWorkers: 'block' })
    page.setDefaultTimeout(8_000)
    const errors = [], external = []
    page.on('pageerror', error => errors.push(error.message))
    page.on('console', message => { if (message.type() === 'error' && message.text().includes('Content Security Policy')) errors.push(message.text()) })
    await page.route('**/*', route => {
      if (new URL(route.request().url()).origin === origin) return route.continue()
      external.push(route.request().url())
      return route.abort('blockedbyclient')
    })
    async function restart(signal) { await close(signal); close = await studio(workspace, port) }
    await run({ page, origin, workspace, restart })
    assert.deepEqual(errors, [])
    assert.deepEqual(external, [])
  } finally { await browser?.close(); await close?.(); await rm(root, { recursive: true, force: true }) }
}

const button = (page, name) => page.getByRole('button', { name, exact: true })
const frameAt = (page, frame) => page.locator(`canvas[data-frame="${frame}"][data-ready="true"]`)
const timelineApi = page => `/api${new URL(page.url()).pathname}`

async function seek(page, frame) {
  await page.getByRole('slider', { name: 'Timeline scrubber' }).fill(String(frame))
  await frameAt(page, frame).waitFor()
}
async function number(page, label, value) {
  const input = page.getByLabel(label, { exact: true })
  await input.fill(String(value))
  await input.press('Enter')
}
async function openSample(page, origin) {
  await page.goto(origin)
  await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'Animation Studio' }).click()
  await visible(page, 'Animation Studio')
  await button(page, 'Open Blue Flower').click()
  await visible(page, 'Blue Flower')
  await frameAt(page, 0).waitFor()
}

// Compare actual canvas pixels, not DOM badges or source keyframe data.
async function lockedPixels(page) {
  return page.locator('canvas').evaluate(async canvas => {
    const ctx = canvas.getContext('2d')
    const regions = [[40,40,460,250], [87,450,143,50], [207,498,114,144]]
    const pixels = await Promise.all(regions.map(async rect => {
      const rgba = ctx.getImageData(...rect).data
      return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', rgba))).join(',')
    }))
    return { forest: pixels[0], eyes: pixels[1], arm: pixels[2] }
  })
}

async function screenshot(page, name) {
  if (!media) return
  await mkdir(media, { recursive: true })
  await page.evaluate(() => window.scrollTo(0,0))
  await page.screenshot({ path: join(media,name) })
}

test('Blue Flower playback, locked canvas and reusable timeline authoring', { timeout: 100_000 }, () => withPage(async ({ page, origin, restart }) => {
  await openSample(page, origin)
  assert.match(await page.getByTestId('motion-frame').textContent(), /^Frame 0 \/ 293$/)
  await button(page, 'Jump to Mina notices the light').click()
  await frameAt(page, 96).waitFor()
  const opened = await lockedPixels(page)
  await button(page, 'Jump to blink').click()
  await frameAt(page, 124).waitFor()
  await button(page, 'Eyes · blink track keyframe 28').click()
  await page.getByText('Keyed', { exact: true }).waitFor()
  await seek(page, 126)
  const blink = await lockedPixels(page)
  await seek(page, 164)
  const gesture = await lockedPixels(page)
  assert.equal(opened.forest, blink.forest)
  assert.equal(opened.forest, gesture.forest)
  assert.notEqual(opened.eyes, blink.eyes)
  assert.notEqual(opened.arm, gesture.arm)
  await screenshot(page, 'blue-flower-editor.png')
  await page.setViewportSize({ width: 390, height: 844 })
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false)
  await screenshot(page, 'blue-flower-narrow.png')
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.getByLabel('Preview speed', { exact: true }).selectOption('0.5')
  await button(page, 'Play animation').click()
  await page.waitForFunction(() => Number(document.querySelector('canvas')?.dataset.frame) > 164)
  await button(page, 'Pause animation').click()
  const paused = Number(await page.locator('canvas').getAttribute('data-frame'))
  await page.waitForTimeout(220)
  await frameAt(page, paused).waitFor()
  await button(page, 'Next frame').click()
  await frameAt(page, paused + 1).waitFor()
  await button(page, 'Jump to Into the bloom').click()
  await frameAt(page, 216).waitFor()
  await page.getByRole('slider', { name: 'Timeline scrubber' }).press('End')
  await frameAt(page, 293).waitFor()
  await button(page, 'Go to start').click()
  await frameAt(page, 0).waitFor()

  await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'Animation Studio' }).click()
  await page.getByLabel('Animation title').fill('Lantern study')
  await button(page, 'New animation').click()
  await visible(page, 'Lantern study')
  const api = timelineApi(page)
  const assetBytes = await readFile(new URL('../../backend/motion/art/bf-hand.webp', import.meta.url))
  await page.getByLabel('Layer image file').setInputFiles({ name: 'Wrist study.webp', mimeType: 'image/webp', buffer: assetBytes })
  await page.getByRole('region', { name: 'Shot layers' }).getByRole('button', { name: /Wrist study/ }).waitFor()
  await frameAt(page,0).waitFor()
  await button(page, 'Add transform group').click()
  await page.getByText('Layer setup & ordering', { exact: true }).click()
  await page.getByLabel('Layer name').fill('Arm pivot')
  await page.getByRole('region', { name: 'Shot layers' }).getByRole('button', { name: /Wrist study/ }).click()
  await page.getByLabel('Parent group or layer').selectOption({ label: 'Arm pivot' })
  await button(page, 'Forward').click()
  await number(page, 'Position X', 260)
  await number(page, 'Position Y', 480)
  await seek(page, 42)
  await number(page, 'Rotation °', -31)
  await number(page, 'Scale X', 1.25)
  await number(page, 'Opacity %', 55)
  await page.getByLabel('Visible at this frame').uncheck()
  await page.getByLabel('Ease into keyframe').selectOption('hold')
  await seek(page, 29)
  await button(page, 'Set keyframe').click()
  await button(page, 'Remove keyframe').click()
  await seek(page, 42)
  await button(page, 'Camera').first().click()
  await page.getByLabel('Camera mode').selectOption('tracking')
  assert.match(await page.getByLabel('Tracking target').locator('option:checked').textContent(), /Arm pivot/)
  await number(page, 'Offset X', -40)
  await number(page, 'Zoom', 1.45)
  await button(page, 'Shot').click()
  await page.getByLabel('Shot name').fill('Alternate angle')
  await number(page, 'Source duration (seconds)', 2)
  await page.getByLabel('Motion speed').selectOption('1.25')
  await page.getByText('60 source frames → 48 output frames at 30 FPS.', { exact: false }).waitFor()
  await button(page, 'Add shot').click()
  await button(page, 'Move shot earlier').click()
  page.once('dialog', dialog => dialog.accept())
  await button(page, 'Remove shot').click()
  await button(page, 'Export MP4').click()
  await page.getByText('Save timeline edits before exporting a new revision.').waitFor()
  assert.equal(await button(page, 'Render MP4').isEnabled(), false)
  await button(page, 'Close export').click()
  await button(page, 'Save timeline').click()
  await page.getByText('Timeline saved on this device.').waitFor()
  const saved = await (await page.request.get(api)).json()
  assert.equal(saved.revision, 2)
  assert.equal(saved.frames, 48)
  assert.equal(saved.shots, 1)
  const [cut] = saved.document.shots
  const [group, wrist] = cut.layers
  assert.equal(group.name, 'Arm pivot')
  assert.equal(wrist.parent, group.id)
  assert.deepEqual(wrist.keys.map(key => [key.frame, key.rotation, key.opacity, key.visible, key.scale_x, key.ease]), [[42,-31,.55,false,1.25,'hold']])
  assert.equal(cut.camera.target, group.id)
  assert.equal(cut.camera.keys[0].x, -40)
  assert.equal(cut.camera.keys[0].zoom, 1.45)
  await restart()
  await page.reload()
  await visible(page, 'Lantern study')
  await frameAt(page, 0).waitFor()
  assert.deepEqual(await (await page.request.get(api)).json(), saved)
}))

test('render, cancel, download and play the exact Blue Flower MP4 locally', { timeout: 245_000, skip: process.env.KOMA_TEST_EXPORT !== '1' }, () => withPage(async ({ page, origin, workspace, restart }) => {
  await openSample(page, origin)
  const api = timelineApi(page), outputs = join(workspace, 'outputs')
  if (media) {
    await mkdir(media, { recursive: true })
    for (const n of [0,95,96,126,164,215,216,251,293]) {
      await seek(page, n)
      const png = await page.locator('canvas').evaluate(el => el.toDataURL('image/png').split(',')[1])
      await writeFile(join(media, `canvas-${n}.png`), Buffer.from(png, 'base64'))
    }
  }
  await button(page, 'Export MP4').click()
  await page.getByLabel('Encoding').selectOption('software')
  let posted = page.waitForResponse(response => response.url().endsWith('/exports') && response.request().method() === 'POST')
  await button(page, 'Render MP4').click({ timeout: 20_000 })
  let response = await posted
  assert.equal(response.status(), 202, await response.text())
  const cancelled = await response.json(), cancelledPath = `${api}/exports/${cancelled.id}`
  await page.waitForFunction(() => document.querySelector('progress')?.value > 0, null, { timeout: 20_000 })
  assert.equal((await page.request.post(`${api}/exports`, { data: { revision: 1, mode: 'software' } })).status(), 409)
  assert.equal((await page.request.get(`${cancelledPath}/video`)).status(), 404)
  await button(page, 'Cancel render').click()
  await page.getByText('cancelled', { exact: true }).waitFor()
  assert.equal((await (await page.request.get(cancelledPath)).json()).state, 'cancelled')
  assert.deepEqual(await readdir(outputs), [])

  // Stop a real render mid-stream. Restart first; the interrupted job must not appear as playable.
  posted = page.waitForResponse(r => r.url().endsWith('/exports') && r.request().method() === 'POST')
  await button(page, 'Render MP4').click()
  response = await posted
  assert.equal(response.status(), 202, await response.text())
  const interrupted = await response.json()
  await page.waitForFunction(() => document.querySelector('progress')?.value > 0, null, {timeout:20_000})
  await restart('SIGKILL')
  assert.equal((await (await page.request.get(`${api}/exports/${interrupted.id}`)).json()).state, 'failed')
  assert.equal((await page.request.get(`${api}/exports/${interrupted.id}/video`)).status(), 404)
  assert.deepEqual(await readdir(outputs), [])

  await page.reload()
  await visible(page, 'Blue Flower')
  await button(page, 'Export MP4').click()
  await page.getByLabel('Encoding').selectOption('auto')
  const begin = performance.now()
  posted = page.waitForResponse(r => r.url().endsWith('/exports') && r.request().method() === 'POST')
  await button(page, 'Render MP4').click()
  response = await posted
  assert.equal(response.status(), 202, await response.text())
  const jobPath = `${api}/exports/${(await response.json()).id}`
  await page.getByText('Complete', { exact: true }).waitFor({ timeout: 180_000 })
  const job = await (await page.request.get(jobPath)).json()
  assert.equal(job.state, 'complete')
  assert.equal(job.done, frames)
  assert.equal(job.frames, frames)
  assert.match(job.encoder, /^(libx264|h264_(?:qsv|nvenc|amf))$/)
  const size = (await stat(job.output_path)).size
  assert.ok(size > 10_000)
  assert.deepEqual(await readdir(outputs), [job.filename])
  const range = await page.request.get(`${jobPath}/video`, { headers: { Range: 'bytes=0-127' } })
  assert.equal(range.status(), 206)
  assert.equal((await range.body()).length, 128)
  console.log(`Blue Flower: ${((performance.now()-begin)/1000).toFixed(2)}s export, ${job.encoder}, ${size} bytes`)

  await button(page, 'Watch export').click()
  const player = page.getByLabel('Exported MP4')
  await page.waitForFunction(() => document.querySelector('video')?.readyState >= 2)
  const metadata = await player.evaluate(v => [v.videoWidth,v.videoHeight,v.duration])
  assert.deepEqual(metadata, [1080,1920,frames/fps])
  await player.evaluate(async v => { v.muted = true; await v.play() })
  await page.waitForFunction(() => document.querySelector('video')?.currentTime > .4)
  await player.evaluate(v => { v.pause(); v.currentTime = 164/30 })
  await page.waitForFunction(() => { const v = document.querySelector('video');return v && !v.seeking && v.currentTime > 5 && v.readyState >= 2 })
  await screenshot(page, 'blue-flower-export.png')
  const downloaded = page.waitForEvent('download')
  await page.getByRole('link', { name: 'Download MP4', exact: true }).click()
  const download = await downloaded
  assert.equal(download.suggestedFilename(), job.filename)
  assert.deepEqual(await readFile(await download.path()), await readFile(job.output_path))
  if (media) await download.saveAs(join(media, 'blue-flower-1080x1920.mp4'))
}))
