async function postSolve(backendUrl, token, payload, attempt = 1) {
  const maxAttempts = 3
  try {
    const res = await fetch(`${backendUrl}/api/capture/solve`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': token,
      },
      body: JSON.stringify(payload),
    })
    const text = await res.text()
    if (!res.ok && res.status >= 500 && attempt < maxAttempts) {
      await new Promise((r) => setTimeout(r, 400 * attempt))
      return postSolve(backendUrl, token, payload, attempt + 1)
    }
    const status = res.ok ? `Sent ${payload.slug}` : `Error ${res.status}: ${text}`
    return { ok: res.ok, status }
  } catch (err) {
    if (attempt < maxAttempts) {
      await new Promise((r) => setTimeout(r, 400 * attempt))
      return postSolve(backendUrl, token, payload, attempt + 1)
    }
    return { ok: false, status: `Network error: ${err}` }
  }
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type !== 'recall.solve') return
  chrome.storage.local.get(['backendUrl', 'apiToken'], async (cfg) => {
    const backendUrl = (cfg.backendUrl || 'http://127.0.0.1:8787').replace(/\/$/, '')
    const token = cfg.apiToken || ''
    const payload = {
      ...message.payload,
      client_event_id:
        message.payload?.client_event_id ||
        `ext-${message.payload?.slug || 'unknown'}-${Date.now()}`,
    }
    const result = await postSolve(backendUrl, token, payload)
    chrome.storage.local.set({ lastStatus: result.status, lastOk: result.ok })
    sendResponse(result)
  })
  return true
})
