/**
 * Render a structure diagram (nodes + edges) to a high-resolution PNG.
 *
 * Workflow:
 *   1. Run dagre layout (TB or LR, auto-picked for canvas aspect 2.33:1)
 *   2. Build inline SVG with red-ringed person circles, red-bordered black
 *      trust triangles, and rounded company rectangles + smoothstep edges
 *      with arrowheads and pill labels
 *   3. Wrap in HTML loading the LC fonts
 *   4. Puppeteer screenshot at 2x DPI scale → crisp PNG ready for python-pptx
 *
 * Usage:
 *   node frontend/scripts/render-diagram.js <input.json> <output.png>
 *
 * Input JSON: {nodes: [...], edges: [...]} — same format as the React Flow
 * editor saves to case_diagrams.
 */
const dagre = require('@dagrejs/dagre')
const fs = require('fs')
const path = require('path')
const puppeteer = require('puppeteer')

const NODE_SIZE = {
  trust: { width: 180, height: 150 },
  company: { width: 220, height: 110 },
  individual: { width: 130, height: 130 },
}
const DEFAULT_SIZE = { width: 220, height: 110 }
const CANVAS_ASPECT = 1680 / 720 // PDF canvas usable area (≈ 2.33)

// Lucide icons (v0.577) — inlined to keep the SVG self-contained.
const ICONS = {
  user:
    '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/>' +
    '<circle cx="12" cy="7" r="4"/>',
  shield:
    '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6' +
    'a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5' +
    'a1 1 0 0 1 1 1z"/>',
  building2:
    '<path d="M10 12h4"/><path d="M10 8h4"/>' +
    '<path d="M14 21v-3a2 2 0 0 0-4 0v3"/>' +
    '<path d="M6 10H4a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-2"/>' +
    '<path d="M6 21V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v16"/>',
}

const escapeHtml = (s) =>
  String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')

function iconSvg(name, size, color) {
  const body = ICONS[name] || ''
  return (
    `<svg viewBox="0 0 24 24" width="${size}" height="${size}" fill="none" ` +
    `stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">` +
    `${body}</svg>`
  )
}

function runDagre(direction, ranksep, nodesep, nodes, edges) {
  const g = new dagre.graphlib.Graph()
  g.setGraph({ rankdir: direction, ranksep, nodesep, marginx: 30, marginy: 30 })
  g.setDefaultEdgeLabel(() => ({}))
  for (const n of nodes) {
    const size = NODE_SIZE[n.type] || DEFAULT_SIZE
    g.setNode(n.id, { width: size.width, height: size.height })
  }
  for (const e of edges) g.setEdge(e.source, e.target)
  dagre.layout(g)

  const laid = nodes.map((n) => {
    const size = NODE_SIZE[n.type] || DEFAULT_SIZE
    const pos = g.node(n.id)
    return {
      id: n.id, type: n.type, data: n.data,
      width: size.width, height: size.height,
      x: pos.x - size.width / 2, y: pos.y - size.height / 2,
    }
  })
  const graph = g.graph()
  return { nodes: laid, width: graph.width, height: graph.height, direction }
}

function renderIndividual(n) {
  const w = n.width
  const cx = w / 2
  const r = 28
  const cy = r + 4
  const d = n.data || {}
  const icon = iconSvg('user', 22, '#E50025')
  return `
    <g>
      <circle cx="${cx}" cy="${cy}" r="${r}" fill="#fafafa" stroke="#E50025" stroke-width="2"/>
      <g transform="translate(${cx - 11},${cy - 11})">${icon}</g>
      <text x="${cx}" y="${cy + r + 18}" text-anchor="middle"
        font-family="Public Sans, sans-serif" font-size="11" font-weight="700" fill="#000">${escapeHtml(d.label || '')}</text>
      ${d.role ? `<text x="${cx}" y="${cy + r + 36}" text-anchor="middle" font-family="Public Sans, sans-serif" font-size="10" font-weight="700" fill="#5a5a5a" letter-spacing="1.2" style="text-transform:uppercase">${escapeHtml(d.role)}</text>` : ''}
      ${d.jurisdiction ? `<text x="${cx}" y="${cy + r + (d.role ? 52 : 36)}" text-anchor="middle" font-family="Public Sans, sans-serif" font-size="10" font-weight="700" fill="#E50025">${escapeHtml(d.jurisdiction)}</text>` : ''}
    </g>`
}

function renderTrust(n) {
  const w = n.width
  const triOff = (w - 160) / 2
  const d = n.data || {}
  const icon = iconSvg('shield', 14, '#E50025')
  return `
    <g>
      <polygon points="${triOff + 80},8 ${triOff + 150},92 ${triOff + 10},92"
        fill="#000" stroke="#E50025" stroke-width="2"/>
      <g transform="translate(${triOff + 80 - 7},30)">${icon}</g>
      <text x="${w / 2}" y="62" text-anchor="middle"
        font-family="Public Sans, sans-serif" font-size="11" font-weight="700" fill="#fff">${escapeHtml(d.label || '')}</text>
      ${d.jurisdiction ? `<text x="${w / 2}" y="110" text-anchor="middle" font-family="Public Sans, sans-serif" font-size="10" font-weight="700" fill="#E50025" letter-spacing="1.2" style="text-transform:uppercase">${escapeHtml(d.jurisdiction)}</text>` : ''}
      ${d.role ? `<text x="${w / 2}" y="${d.jurisdiction ? 126 : 110}" text-anchor="middle" font-family="Public Sans, sans-serif" font-size="10" fill="#5a5a5a">${escapeHtml(d.role)}</text>` : ''}
    </g>`
}

function renderCompany(n) {
  const w = n.width
  const h = n.height
  const d = n.data || {}
  const icon = iconSvg('building2', 12, '#5a5a5a')
  return `
    <g>
      <rect x="0" y="0" width="${w}" height="${h}" rx="6" ry="6"
        fill="#fafafa" stroke="#cdcdcd" stroke-width="1"/>
      <g transform="translate(16,18)">${icon}</g>
      <text x="${w / 2}" y="32" text-anchor="middle"
        font-family="Public Sans, sans-serif" font-size="11" font-weight="700" fill="#000">${escapeHtml(d.label || '')}</text>
      ${d.jurisdiction ? `<text x="${w / 2}" y="60" text-anchor="middle" font-family="Public Sans, sans-serif" font-size="10" font-weight="700" fill="#E50025" letter-spacing="1.2" style="text-transform:uppercase">${escapeHtml(d.jurisdiction)}</text>` : ''}
      ${d.role ? `<text x="${w / 2}" y="${d.jurisdiction ? 78 : 60}" text-anchor="middle" font-family="Public Sans, sans-serif" font-size="10" fill="#5a5a5a">${escapeHtml(d.role)}</text>` : ''}
    </g>`
}

function renderNode(n) {
  let body
  if (n.type === 'trust') body = renderTrust(n)
  else if (n.type === 'company') body = renderCompany(n)
  else body = renderIndividual(n)
  return `<g transform="translate(${n.x},${n.y})">${body}</g>`
}

function renderEdge(e, byId, direction) {
  const s = byId[e.source]
  const t = byId[e.target]
  if (!s || !t) return ''
  let sx, sy, tx, ty, path
  if (direction === 'LR') {
    sx = s.x + s.width
    sy = s.y + s.height / 2
    tx = t.x
    ty = t.y + t.height / 2
    const midX = (sx + tx) / 2
    path = `M ${sx},${sy} C ${midX},${sy} ${midX},${ty} ${tx},${ty}`
  } else {
    sx = s.x + s.width / 2
    sy = s.y + s.height
    tx = t.x + t.width / 2
    ty = t.y
    const midY = (sy + ty) / 2
    path = `M ${sx},${sy} C ${sx},${midY} ${tx},${midY} ${tx},${ty}`
  }
  let out = `<path d="${path}" fill="none" stroke="#6c6c6c" stroke-opacity="0.55" stroke-width="1.5" marker-end="url(#arr)"/>`
  if (e.label) {
    const mx = (sx + tx) / 2
    const my = (sy + ty) / 2
    const tw = Math.max(28, e.label.length * 6.5 + 14)
    const th = 20
    out += `
      <g transform="translate(${mx - tw / 2},${my - th / 2})">
        <rect width="${tw}" height="${th}" rx="4" ry="4" fill="#000" fill-opacity="0.85"/>
        <text x="${tw / 2}" y="${th / 2 + 4}" text-anchor="middle"
          font-family="Public Sans, sans-serif" font-size="11" font-weight="600" fill="#fff">${escapeHtml(e.label)}</text>
      </g>`
  }
  return out
}

function buildSvg(nodes, edges, direction) {
  if (!nodes.length) return '<svg/>'
  const minX = Math.min(...nodes.map((n) => n.x))
  const minY = Math.min(...nodes.map((n) => n.y))
  const maxX = Math.max(...nodes.map((n) => n.x + n.width))
  const maxY = Math.max(...nodes.map((n) => n.y + n.height))
  const padX = 40
  const padY = 56
  const w = maxX - minX + 2 * padX
  const h = maxY - minY + 2 * padY
  const byId = Object.fromEntries(nodes.map((n) => [n.id, n]))
  const edgeSvg = edges.map((e) => renderEdge(e, byId, direction)).join('')
  const nodeSvg = nodes.map(renderNode).join('')
  return `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${h}"
      width="${w}" height="${h}" preserveAspectRatio="xMidYMid meet">
      <defs>
        <marker id="arr" viewBox="0 0 10 10" refX="9" refY="5"
          markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M0,0 L10,5 L0,10 z" fill="#6c6c6c" fill-opacity="0.85"/>
        </marker>
      </defs>
      <g transform="translate(${padX - minX},${padY - minY})">
        ${edgeSvg}
        ${nodeSvg}
      </g>
    </svg>`
}

async function main() {
  const [, , inputPath, outputPath] = process.argv
  if (!inputPath || !outputPath) {
    console.error('usage: render-diagram.js <input.json> <output.png>')
    process.exit(2)
  }
  const { nodes = [], edges = [] } = JSON.parse(fs.readFileSync(inputPath, 'utf8'))
  if (!nodes.length) {
    console.error('no nodes in diagram')
    process.exit(3)
  }

  // Pick orientation that fits the slide canvas best
  const tb = runDagre('TB', 140, 110, nodes, edges)
  const lr = runDagre('LR', 200, 80, nodes, edges)
  const score = (g) => Math.abs(Math.log(g.width / Math.max(g.height, 1) / CANVAS_ASPECT))
  const best = score(lr) < score(tb) ? lr : tb

  const svg = buildSvg(best.nodes, edges, best.direction)

  // Compute pixel dimensions for the screenshot. Aim for ~3.5x scale-up so
  // the rendered PNG is crisp when embedded at slide scale (1680px wide).
  const minX = Math.min(...best.nodes.map((n) => n.x))
  const minY = Math.min(...best.nodes.map((n) => n.y))
  const maxX = Math.max(...best.nodes.map((n) => n.x + n.width))
  const maxY = Math.max(...best.nodes.map((n) => n.y + n.height))
  const svgW = maxX - minX + 80
  const svgH = maxY - minY + 112
  // Render the SVG at a size that targets ~3000px on the longer axis
  const scale = 3000 / Math.max(svgW, svgH)
  const renderW = Math.round(svgW * scale)
  const renderH = Math.round(svgH * scale)

  // Fonts ship with the LC PowerPoint skill, vendored under
  // backend/skills/lighthouse-canton-ppt/assets/fonts/. Keeping a single
  // source of truth avoids the old backend/templates/lc-deck duplicate.
  const fontDir = path.resolve(__dirname, '..', '..', 'backend', 'skills', 'lighthouse-canton-ppt', 'assets', 'fonts').replace(/\\/g, '/')
  const html = `<!doctype html>
<html><head><meta charset="utf-8"/>
<style>
  @font-face { font-family: 'Public Sans'; src: url('file://${fontDir}/PublicSans-VariableFont_wght.ttf') format('truetype-variations'); font-weight: 100 900; }
  @font-face { font-family: 'Frank Ruhl Libre'; src: url('file://${fontDir}/FrankRuhlLibre-VariableFont_wght.ttf') format('truetype-variations'); font-weight: 300 900; }
  html, body { margin: 0; padding: 0; background: #fff; }
  .stage { width: ${renderW}px; height: ${renderH}px; display: flex; align-items: center; justify-content: center; }
  .stage svg { width: 100%; height: 100%; }
</style></head>
<body><div class="stage">${svg}</div></body></html>`

  const browser = await puppeteer.launch({
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  })
  try {
    const page = await browser.newPage()
    await page.setViewport({ width: renderW, height: renderH, deviceScaleFactor: 2 })
    await page.setContent(html, { waitUntil: 'networkidle0' })
    // Give fonts a moment to load
    await page.evaluate(() => document.fonts.ready)
    const stage = await page.$('.stage')
    await stage.screenshot({ path: outputPath, omitBackground: false })
    process.stdout.write(JSON.stringify({
      direction: best.direction,
      width: renderW,
      height: renderH,
      svgWidth: svgW,
      svgHeight: svgH,
    }))
  } finally {
    await browser.close()
  }
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
