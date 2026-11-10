/*
 * No-install E2E smoke check for the actual frontend upload function against
 * a running FastAPI server at http://127.0.0.1:18081.
 * Uses Node 22's native Fetch + FormData + File (same browser API contract).
 */
import fs from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import assert from 'node:assert/strict'

const current = dirname(fileURLToPath(import.meta.url))
const js = fs.readFileSync(resolve(current, '../frontend/src/api.js'), 'utf8')
  .replace('import.meta.env.VITE_API_BASE_URL', "'http://127.0.0.1:18081'")
const { validateImageWithBackend } = await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`)

const png = fs.readFileSync(resolve(current, 'fixtures/sample.png'))
const file = new File([png], 'photo.png', {type:'image/png'})
const accepted = await validateImageWithBackend(file, 'A')
assert.equal(accepted.status, 'accepted')
assert.equal(accepted.participant_id, 'A')
assert.equal(accepted.image_format, 'png')
assert.equal(accepted.width, 944)
assert.equal(accepted.height, 2048)
assert.equal(accepted.image_persisted, false)
console.log('PASS: real PNG -> frontend upload function -> FastAPI -> accepted')

const cameraJpg = new File([fs.readFileSync(resolve(current, 'fixtures/camera_test.jpg'))], 'camera_A.jpg', {type:'image/jpeg'})
const cameraAccepted = await validateImageWithBackend(cameraJpg, 'B')
assert.equal(cameraAccepted.status, 'accepted')
assert.equal(cameraAccepted.image_format, 'jpeg')
assert.equal(cameraAccepted.width, 900)
console.log('PASS: camera-style JPEG -> frontend upload function -> FastAPI')

const webp = new File([fs.readFileSync(resolve(current, 'fixtures/webp_test.webp'))], 'finger.webp', {type:'image/webp'})
const webpAccepted = await validateImageWithBackend(webp, 'C')
assert.equal(webpAccepted.status, 'accepted')
assert.equal(webpAccepted.image_format, 'webp')
console.log('PASS: WebP upload -> FastAPI')

const invalid = new File([Buffer.from('not a jpeg')], 'bad.jpg', {type:'image/jpeg'})
await assert.rejects(validateImageWithBackend(invalid, 'B'), /画像を読み取れません/)
console.log('PASS: corrupt JPEG -> proper Japanese error')

const unsupported = new File([png], 'bad.gif', {type:'image/gif'})
await assert.rejects(validateImageWithBackend(unsupported, 'C'), /JPEG・PNG・WebP/)
console.log('PASS: unsupported MIME -> rejection')

const mismatch = new File([png], 'wrong.jpg', {type:'image/jpeg'})
await assert.rejects(validateImageWithBackend(mismatch, 'A'), /画像の内容と形式が一致/)
console.log('PASS: mismatching file bytes and MIME -> rejection')

const noFile = new File([], 'empty.jpg', {type:'image/jpeg'})
await assert.rejects(validateImageWithBackend(noFile, 'A'), /画像ファイルが選択されていません/)
console.log('PASS: empty file -> rejection')
