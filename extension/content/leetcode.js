(() => {
  const state = {
    slug: null,
    title: '',
    difficulty: 'Medium',
    tags: [],
    openedAt: Date.now(),
    firstKeyAt: null,
    hiddenMs: 0,
    hiddenSince: null,
    submissions: 0,
    sent: false,
    clientEventId: null,
  }

  function slugFromUrl() {
    const m = location.pathname.match(/\/problems\/([^/]+)/)
    return m ? m[1] : null
  }

  // LeetCode DOM churns; these few selectors break often — adjust when capture fails.
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
      openedAt: Date.now(),
      firstKeyAt: null,
      hiddenMs: 0,
      hiddenSince: null,
      submissions: 0,
      sent: false,
      clientEventId: crypto.randomUUID(),
    })
    readMeta()
  }

  function visibleSeconds(from, to) {
    const raw = Math.max(0, to - from - state.hiddenMs)
    return Math.min(3600, Math.round(raw / 1000))
  }

  function onKey() {
    if (!state.firstKeyAt) state.firstKeyAt = Date.now()
  }

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) state.hiddenSince = Date.now()
    else if (state.hiddenSince) {
      state.hiddenMs += Date.now() - state.hiddenSince
      state.hiddenSince = null
    }
  })

  document.addEventListener('keydown', onKey, true)

  function maybeAccepted(text) {
    return /accepted/i.test(text) && !/not accepted/i.test(text)
  }

  function send(verdict) {
    if (state.sent || !state.slug) return
    state.sent = true
    const now = Date.now()
    const understand = state.firstKeyAt
      ? visibleSeconds(state.openedAt, state.firstKeyAt)
      : visibleSeconds(state.openedAt, now)
    const write = state.firstKeyAt ? visibleSeconds(state.firstKeyAt, now) : null
    chrome.runtime.sendMessage({
      type: 'recall.solve',
      payload: {
        client_event_id: state.clientEventId,
        platform: 'leetcode',
        slug: state.slug,
        title: state.title || state.slug,
        url: location.href.split('?')[0],
        difficulty: state.difficulty,
        verdict,
        time_to_understand_s: understand,
        time_to_write_s: write,
        num_submissions: Math.max(1, state.submissions),
        hints_used: 0,
        tags: state.tags,
        auto_review: true,
      },
    })
  }

  const observer = new MutationObserver(() => {
    const bodyText = document.body?.innerText?.slice(0, 20000) || ''
    if (/submit/i.test(bodyText)) {
      // count clicks on submit-ish buttons opportunistically via click listener below
    }
    if (maybeAccepted(bodyText)) send('Accepted')
  })
  observer.observe(document.documentElement, { childList: true, subtree: true, characterData: true })

  document.addEventListener('click', (e) => {
    const t = e.target
    if (!(t instanceof HTMLElement)) return
    const label = `${t.innerText || ''} ${t.getAttribute('data-e2e-locator') || ''}`.toLowerCase()
    if (label.includes('submit')) state.submissions += 1
  }, true)

  // SPA navigation — skip work while the tab is hidden
  let last = slugFromUrl()
  if (last) resetForSlug(last)
  setInterval(() => {
    if (document.hidden) return
    const s = slugFromUrl()
    if (s && s !== last) {
      last = s
      resetForSlug(s)
    } else {
      readMeta()
    }
  }, 1000)
})()
