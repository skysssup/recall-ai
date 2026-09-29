const urlEl = document.getElementById('url')
const tokenEl = document.getElementById('token')
const statusEl = document.getElementById('status')

chrome.storage.local.get(['backendUrl', 'apiToken', 'lastStatus'], (data) => {
  urlEl.value = data.backendUrl || 'http://127.0.0.1:8787'
  tokenEl.value = data.apiToken || ''
  statusEl.textContent = data.lastStatus || 'Not configured'
})

document.getElementById('save').addEventListener('click', () => {
  chrome.storage.local.set({
    backendUrl: urlEl.value.trim().replace(/\/$/, ''),
    apiToken: tokenEl.value.trim(),
  }, () => {
    statusEl.textContent = 'Saved'
  })
})
