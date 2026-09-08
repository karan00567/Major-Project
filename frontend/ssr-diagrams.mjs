// Server-renders the three model-architecture components to standalone .svg so
// the same figures can be dropped into the report and the slide deck without
// screenshotting the browser. Run it with `npm run diagrams [outDir]`.
//
// Two things it has to undo before the SVG stands alone: Vue's SSR lowercases
// `viewBox` (HTML parsers forgive that, XML does not), and the components size
// themselves with width="100%", which leaves a standalone file with no
// intrinsic size for PowerPoint to scale.
import fs from 'node:fs'
import path from 'node:path'
import { createServer } from 'vite'
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'

const OUT = process.argv[2] || './__svg'
fs.mkdirSync(OUT, { recursive: true })

// The light-theme values of the tokens in style.css, resolved so the file
// stands alone. Kept in one string so a drift is obvious.
const CSS = `
  svg { font-family: system-ui, 'Segoe UI', Roboto, sans-serif; background:#ffffff; }
  .arch-box{fill:#fff;stroke:#e3e5e9}
  .arch-box-muted{fill:#eff1f5;stroke:#e3e5e9}
  .arch-box-accent{fill:rgba(47,111,237,.09);stroke:#2f6fed}
  .arch-box-good{fill:rgba(47,158,95,.10);stroke:#2f9e5f}
  .arch-box-warn{fill:rgba(201,138,46,.11);stroke:#c98a2e}
  .arch-box-bad{fill:rgba(217,83,79,.10);stroke:#d9534f}
  .arch-box-alt{fill:rgba(142,68,173,.09);stroke:#8e44ad}
  .arch-title{fill:#1a1c1f;font-size:13px;font-weight:600}
  .arch-sub{fill:#6b7280;font-size:10.5px}
  .arch-mono{fill:#6b7280;font-size:10.5px;font-family:ui-monospace,Consolas,monospace}
  .arch-cap{fill:#7d8490;font-size:10px}
  .arch-lane{fill:#6b7280;font-size:11px;font-weight:600;letter-spacing:.06em;text-transform:uppercase}
  .arch-line{stroke:#6b7280;fill:none;stroke-width:1.5}
  .arch-line-soft{stroke:#e3e5e9;fill:none;stroke-width:1.5}
  .arch-arrowhead{fill:#6b7280}
  .arch-group{fill:none;stroke:#e3e5e9;stroke-dasharray:4 4}
`

const vite = await createServer({
  server: { middlewareMode: true },
  appType: 'custom',
  logLevel: 'warn',
})

for (const name of ['RankerArch', 'SummaryArch', 'VerifierArch']) {
  const mod = await vite.ssrLoadModule(`/src/components/diagrams/${name}.vue`)
  let svg = await renderToString(createSSRApp(mod.default))
  svg = svg.replace(/<!--[\s\S]*?-->/g, '')
  // Give it an xmlns and drop the CSS in, so the file opens on its own.
  // `width="100%"` is what the app wants but leaves a standalone file with no
  // intrinsic size, which importers resolve by guessing — replace it with the
  // viewBox extent so the file measures the same everywhere.
  // Vue's SSR lowercases attribute names. An HTML parser silently corrects
  // `viewbox` back to `viewBox` for foreign content, so the app is unaffected —
  // a standalone .svg parsed as XML is not, so restore the camelCase here.
  const [, vw, vh] = svg.match(/viewbox="0 0 (\d+) (\d+)"/i)
  svg = svg.replace('<svg ', '<svg xmlns="http://www.w3.org/2000/svg" ')
           .replace(/viewbox=/i, 'viewBox=')
           .replace('width="100%"', `width="${vw}" height="${vh}"`)
           .replace(/(<svg[^>]*>)/, `$1<style>${CSS}</style>`)
  const file = path.join(OUT, `${name}.svg`)
  fs.writeFileSync(file, svg)
  console.log('wrote', file, svg.length, 'bytes')
}

await vite.close()
