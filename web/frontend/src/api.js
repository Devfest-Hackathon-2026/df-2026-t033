/**
 * Upload a fingerprint image for temporary server-side format checks.
 * Fingerprint analysis and music synthesis still run locally in the browser.
 */
const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

export async function validateImageWithBackend(file, participantId) {
  if (!(file instanceof Blob) || !file.size) throw new Error('画像ファイルが選択されていません。')
  const form = new FormData()
  form.append('participant_id', participantId)
  form.append('consent', 'true')
  form.append('image', file, file.name || 'fingerprint.jpg')

  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 20000)
  try {
    // Do not set Content-Type: fetch supplies the multipart boundary automatically.
    const response = await fetch(`${API_BASE}/api/images/validate`, {
      method: 'POST',
      body: form,
      signal: controller.signal,
      cache: 'no-store',
    })
    const contentType = response.headers.get('content-type') || ''
    const result = contentType.includes('application/json')
      ? await response.json().catch(() => null)
      : null

    if (!response.ok) {
      if (response.status === 502 || response.status === 503 || response.status === 504) {
        throw new Error('画像受付サーバーに接続できません。バックエンドが起動しているか確認してください。')
      }
      throw new Error(result?.message || `画像を送信できませんでした（HTTP ${response.status}）。`)
    }
    if (result?.status !== 'accepted' || result?.participant_id !== participantId) {
      throw new Error('画像受付サーバーからの応答が不正です。')
    }
    return result
  } catch (error) {
    if (error?.name === 'AbortError') throw new Error('画像送信がタイムアウトしました。再試行してください。')
    if (error instanceof TypeError) {
      throw new Error('画像受付サーバーに接続できません。バックエンドが起動しているか確認してください。')
    }
    throw error
  } finally {
    clearTimeout(timeout)
  }
}
