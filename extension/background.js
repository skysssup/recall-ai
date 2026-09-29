chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type !== 'recall.solve') return
  chrome.storage.local.get(['backendUrl', 'apiToken'], async (cfg) => {
    const backendUrl = (cfg.backendUrl || 'http://127.0.0.1:8787').replace(/\/$/, '')
    const token = cfg.apiToken || ''
    try {
      const res = await fetch(`${backendUrl}/api/capture/solve`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': token,
        },
        body: JSON.stringify(message.payload),
      })
      const text = await res.text()
      const status = res.ok ? `Sent ${message.payload.slug}` : `Error ${res.status}: ${text}`
      chrome.storage.local.set({ lastStatus: status })
      sendResponse({ ok: res.ok, status })
    } catch (err) {
      const status = `Network error: ${err}`
      chrome.storage.local.set({ lastStatus: status })
      sendResponse({ ok: false, status })
    }
  })
  return true
})
