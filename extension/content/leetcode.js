(() => {
  const state = {
    slug: null,
    title: '',
    difficulty: 'Medium',
    tags: [],
    visibleMs: 0,
    visibleSince: null,
    firstKeyMs: null,
    submissions: 0,
    awaitingResult: false,
    resultBeforeSubmit: '',
    resultChanged: false,
    inFlight: false,
    delivered: false,
    payload: null,
    retryAt: 0,
    retryDelay: 5000,
    clientEventId: null,
  }

  function slugFromUrl() {
    const m = location.pathname.match(/\/problems\/([^/]+)/)
    return m ? m[1] : null
  }

  function readMeta() {
    const titleEl =
      document.querySelector('[data-cy="question-title"]') ||
      document.querySelector('div[class*="text-title"]') ||
      document.querySelector('h1')
    if (titleEl) state.title = titleEl.textContent.trim()

    const diff =
      document.querySelector('[diff]') ||
      document.querySelector('.text-difficulty-easy, .text-difficulty-medium, .text-difficulty-hard') ||
      document.querySelector('[class*="difficulty"]')
    const raw = (diff?.textContent || '').trim()
    if (/easy/i.test(raw)) state.difficulty = 'Easy'
    else if (/hard/i.test(raw)) state.difficulty = 'Hard'
    else if (/medium/i.test(raw)) state.difficulty = 'Medium'

    const tagEls = document.querySelectorAll('a[href*="/tag/"], a[href*="/topic/"]')
    state.tags = Array.from(tagEls)
      .map((a) => a.textContent.trim())
      .filter(Boolean)
      .slice(0, 8)
  }

  function resetForSlug(slug) {
    Object.assign(state, {
      slug,
      title: slug,
      difficulty: 'Medium',
      tags: [],
      visibleMs: 0,
      visibleSince: document.hidden ? null : Date.now(),
      firstKeyMs: null,
      submissions: 0,
      awaitingResult: false,
      resultBeforeSubmit: '',
      resultChanged: false,
      inFlight: false,
      delivered: false,
      payload: null,
      retryAt: 0,
      retryDelay: 5000,
      clientEventId: crypto.randomUUID(),
    })
    readMeta()
  }

  function syncSlug() {
    const slug = slugFromUrl()
    if (slug !== state.slug) resetForSlug(slug)
  }

  function visibleMillis() {
    return state.visibleMs + (state.visibleSince === null ? 0 : Date.now() - state.visibleSince)
  }

  document.addEventListener('visibilitychange', () => {
    syncSlug()
    if (document.hidden) {
      state.visibleMs = visibleMillis()
      state.visibleSince = null
    } else if (state.visibleSince === null) {
      state.visibleSince = Date.now()
    }
  })

  function result() {
    const node = document.querySelector(
      '[data-e2e-locator="submission-result"], [data-cy="submission-result"], [data-cy="judge-status"]',
    )
    return node?.textContent.trim() || ''
  }

  function submitted() {
    syncSlug()
    if (!state.slug || state.delivered || state.payload) return
    state.submissions += 1
    state.awaitingResult = true
    state.resultBeforeSubmit = result()
    state.resultChanged = false
    readMeta()
  }

  async function deliver() {
    if (!state.payload || state.inFlight || state.delivered || Date.now() < state.retryAt) return
    const eventId = state.clientEventId
    state.inFlight = true
    try {
      const response = await chrome.runtime.sendMessage({ type: 'recall.solve', payload: state.payload })
      if (state.clientEventId === eventId) state.delivered = response?.ok === true
    } catch {
      // A suspended extension worker can reject before returning a delivery status.
    } finally {
      if (state.clientEventId === eventId) {
        state.inFlight = false
        state.retryAt = Date.now() + state.retryDelay
        state.retryDelay = Math.min(60000, state.retryDelay * 2)
      }
    }
  }

  const observer = new MutationObserver(() => {
    syncSlug()
    if (!state.awaitingResult || state.payload) return
    const current = result()
    if (current !== state.resultBeforeSubmit) {
      state.resultChanged = true
    }
    if (state.resultChanged && /^(?:not accepted|wrong answer|time limit exceeded|memory limit exceeded|output limit exceeded|runtime error|compile error|internal error|unknown error)$/i.test(current)) {
      state.awaitingResult = false
      return
    }
    // An accepted verdict already on screen belongs to an earlier submission.
    if (!state.resultChanged || !/^accepted$/i.test(current)) return
    const visible = visibleMillis()
    const seconds = (ms) => Math.min(3600, Math.round(Math.max(0, ms) / 1000))
    state.awaitingResult = false
    state.payload = {
      client_event_id: state.clientEventId,
      platform: 'leetcode',
      slug: state.slug,
      title: state.title || state.slug,
      url: location.href.split('?')[0],
      difficulty: state.difficulty,
      verdict: 'Accepted',
      time_to_understand_s: seconds(state.firstKeyMs ?? visible),
      time_to_write_s: state.firstKeyMs === null ? null : seconds(visible - state.firstKeyMs),
      num_submissions: state.submissions,
      hints_used: 0,
      tags: state.tags,
      auto_review: true,
    }
    void deliver()
  })
  observer.observe(document.documentElement, { childList: true, subtree: true, characterData: true })

  document.addEventListener('click', (e) => {
    if (!e.isTrusted || !(e.target instanceof Element)) return
    const button = e.target.closest('button, [role="button"]')
    if (!button || button.disabled || button.getAttribute('aria-disabled') === 'true') return
    const label = button.getAttribute('aria-label') || button.textContent.trim()
    if (button.getAttribute('data-e2e-locator') === 'console-submit-button' || /^submit(?: code)?$/i.test(label)) submitted()
  }, true)

  document.addEventListener('keydown', (e) => {
    if (!e.isTrusted || e.repeat) return
    syncSlug()
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      submitted()
    } else if (state.firstKeyMs === null && e.target instanceof Element && e.target.closest('.monaco-editor, .CodeMirror')) {
      state.firstKeyMs = visibleMillis()
    }
  }, true)

  syncSlug()
  setInterval(() => {
    syncSlug()
    if (!document.hidden) readMeta()
    void deliver()
  }, 1000)
})()
