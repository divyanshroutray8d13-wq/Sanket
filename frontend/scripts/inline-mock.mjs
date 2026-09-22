// Preview build only: embeds the mock JSON into dist/index.html,
// because a single shared HTML file cannot fetch /mock/*.json.
import { existsSync, readFileSync, writeFileSync, readdirSync } from 'node:fs'

const mocks = {}
for (const f of readdirSync('public/mock')) {
  if (f.endsWith('.json')) mocks[f.replace('.json', '')] = JSON.parse(readFileSync(`public/mock/${f}`, 'utf8'))
}
const html = readFileSync('dist/index.html', 'utf8')
// Real results win over the sample, same as on the live site
const resultsFile = ['public/results.json', 'public/results.sample.json'].find((f) => existsSync(f))
const results = resultsFile ? readFileSync(resultsFile, 'utf8') : 'null'
const tag = `<script>window.__SANKET_MOCK__=${JSON.stringify(mocks)};window.__SANKET_RESULTS__=${results}</script>`
writeFileSync('dist/index.html', html.replace('<head>', `<head>${tag}`))
console.log('Inlined mocks:', Object.keys(mocks).join(', '))
