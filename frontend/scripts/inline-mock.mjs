// Preview build only: embeds the mock JSON into dist/index.html,
// because a single shared HTML file cannot fetch /mock/*.json.
import { readFileSync, writeFileSync, readdirSync } from 'node:fs'

const mocks = {}
for (const f of readdirSync('public/mock')) {
  if (f.endsWith('.json')) mocks[f.replace('.json', '')] = JSON.parse(readFileSync(`public/mock/${f}`, 'utf8'))
}
const html = readFileSync('dist/index.html', 'utf8')
const tag = `<script>window.__SANKET_MOCK__=${JSON.stringify(mocks)}</script>`
writeFileSync('dist/index.html', html.replace('<head>', `<head>${tag}`))
console.log('Inlined mocks:', Object.keys(mocks).join(', '))
