import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const assetsDir = path.resolve(__dirname, '../../dist/assets')

const kb = 1024
const budgets = {
  jsAssetMax: Number(process.env.BUNDLE_JS_ASSET_MAX_BYTES || 550 * kb),
  cssAssetMax: Number(process.env.BUNDLE_CSS_ASSET_MAX_BYTES || 220 * kb),
  totalJsMax: Number(process.env.BUNDLE_TOTAL_JS_MAX_BYTES || 1700 * kb),
  totalCssMax: Number(process.env.BUNDLE_TOTAL_CSS_MAX_BYTES || 320 * kb),
}

function formatBytes(bytes) {
  if (bytes < kb) return `${bytes} B`
  if (bytes < kb * kb) return `${(bytes / kb).toFixed(1)} KB`
  return `${(bytes / (kb * kb)).toFixed(2)} MB`
}

if (!fs.existsSync(assetsDir)) {
  console.error(`Bundle assets not found: ${assetsDir}`)
  process.exit(1)
}

const files = fs
  .readdirSync(assetsDir, { withFileTypes: true })
  .filter((entry) => entry.isFile())
  .map((entry) => {
    const fullPath = path.join(assetsDir, entry.name)
    const size = fs.statSync(fullPath).size
    const ext = path.extname(entry.name)
    return { name: entry.name, size, ext }
  })

const jsFiles = files.filter((file) => file.ext === '.js').sort((a, b) => b.size - a.size)
const cssFiles = files.filter((file) => file.ext === '.css').sort((a, b) => b.size - a.size)

const totalJs = jsFiles.reduce((sum, file) => sum + file.size, 0)
const totalCss = cssFiles.reduce((sum, file) => sum + file.size, 0)

const failures = [
  ...jsFiles
    .filter((file) => file.size > budgets.jsAssetMax)
    .map((file) => `JS chunk ${file.name} exceeds budget: ${formatBytes(file.size)} > ${formatBytes(budgets.jsAssetMax)}`),
  ...cssFiles
    .filter((file) => file.size > budgets.cssAssetMax)
    .map((file) => `CSS asset ${file.name} exceeds budget: ${formatBytes(file.size)} > ${formatBytes(budgets.cssAssetMax)}`),
]

if (totalJs > budgets.totalJsMax) {
  failures.push(`Total JS exceeds budget: ${formatBytes(totalJs)} > ${formatBytes(budgets.totalJsMax)}`)
}

if (totalCss > budgets.totalCssMax) {
  failures.push(`Total CSS exceeds budget: ${formatBytes(totalCss)} > ${formatBytes(budgets.totalCssMax)}`)
}

console.log('Bundle budget report')
console.log(`Assets dir: ${assetsDir}`)
console.log(`Total JS: ${formatBytes(totalJs)}`)
console.log(`Total CSS: ${formatBytes(totalCss)}`)

if (jsFiles.length > 0) {
  console.log('\nLargest JS chunks:')
  jsFiles.slice(0, 8).forEach((file) => {
    console.log(`- ${file.name}: ${formatBytes(file.size)}`)
  })
}

if (cssFiles.length > 0) {
  console.log('\nLargest CSS assets:')
  cssFiles.slice(0, 5).forEach((file) => {
    console.log(`- ${file.name}: ${formatBytes(file.size)}`)
  })
}

if (failures.length > 0) {
  console.error('\nBundle budget failures:')
  failures.forEach((failure) => console.error(`- ${failure}`))
  process.exit(1)
}

console.log('\nBundle budgets: OK')
