/**
 * Render an LC HTML deck to one PNG per <section>. Used for visual QA so the
 * agent can `Read` each rendered slide instead of asking the user for
 * screenshots.
 *
 * Usage:
 *   node frontend/scripts/render-screenshots.js <html-path> <out-dir>
 *
 * Writes <out-dir>/slide-01.png, slide-02.png, ... at 1920x1080 each.
 */
const puppeteer = require('puppeteer')
const path = require('path')
const fs = require('fs')

async function main() {
  const [, , htmlPath, outDir] = process.argv
  if (!htmlPath || !outDir) {
    console.error('usage: render-screenshots.js <html-path> <out-dir>')
    process.exit(2)
  }
  fs.mkdirSync(outDir, { recursive: true })

  const browser = await puppeteer.launch({
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  })
  try {
    const page = await browser.newPage()
    await page.setViewport({ width: 1920, height: 1080, deviceScaleFactor: 1 })
    const url = 'file://' + path.resolve(htmlPath).replace(/\\/g, '/')
    await page.goto(url, { waitUntil: 'networkidle0', timeout: 30000 })

    const sectionCount = await page.evaluate(
      () => document.querySelectorAll('section.slide').length,
    )

    // Resize viewport so the entire document fits — every section is then in
    // view, no scrolling needed, and per-section clips work directly.
    await page.setViewport({
      width: 1920,
      height: sectionCount * 1080,
      deviceScaleFactor: 1,
    })
    // Force layout to settle at the new viewport size.
    await new Promise((r) => setTimeout(r, 200))

    for (let i = 0; i < sectionCount; i++) {
      const file = path.join(outDir, `slide-${String(i + 1).padStart(2, '0')}.png`)
      await page.screenshot({
        path: file,
        clip: { x: 0, y: i * 1080, width: 1920, height: 1080 },
        type: 'png',
      })
      console.log(`wrote ${file}`)
    }
  } finally {
    await browser.close()
  }
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
