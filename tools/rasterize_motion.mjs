// Authoring only. Uses the test-only Chromium driver; no browser binary is downloaded here.
import { createRequire } from 'node:module'
import { mkdir, readdir, readFile } from 'node:fs/promises'
import { join } from 'node:path'
const { chromium } = createRequire(new URL('../tests/browser/package.json', import.meta.url))('playwright-core')
const [source, destination] = process.argv.slice(2)
const browser = await chromium.launch({ executablePath: process.env.KOMA_CHROMIUM_EXECUTABLE,
  args: JSON.parse(process.env.KOMA_CHROMIUM_ARGS || '[]') })
try {
  await mkdir(destination, { recursive: true })
  const page = await browser.newPage()
  for (const file of (await readdir(source)).filter(name => name.endsWith('.svg'))) {
    const svg = await readFile(join(source, file), 'utf8')
    const [, width, height] = svg.match(/width="(\d+)" height="(\d+)"/)
    await page.setViewportSize({ width: Number(width), height: Number(height) })
    await page.setContent(`<style>html,body{margin:0;overflow:hidden}</style>${svg}`)
    await page.screenshot({ path: join(destination, file.replace('.svg','.png')), omitBackground: true })
  }
} finally { await browser.close() }
