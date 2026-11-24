import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { readdirSync } from 'node:fs'

const files = readdirSync(new URL('.', import.meta.url), { withFileTypes: true })
  .filter(entry => entry.isFile() && entry.name.endsWith('.test.mjs'))
  .map(entry => `tests/unit/${entry.name}`)
  .sort()

assert(files.length > 0, 'No unit test files found in tests/unit')

const result = spawnSync(process.execPath, ['--import=tsx', '--test', ...files], {
  cwd: new URL('../../', import.meta.url),
  stdio: 'inherit',
})
if (result.error) throw result.error
process.exitCode = result.status ?? 1
