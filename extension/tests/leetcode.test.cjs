const { test } = require('node:test')
const assert = require('node:assert/strict')
const { readFileSync } = require('node:fs')
const { runInNewContext } = require('node:vm')

const source = readFileSync(`${__dirname}/../content/leetcode.js`, 'utf8')

function page(send = async () => ({ ok: true })) {
  let now = 0
  let observe, tick
  let verdict = null
  let sequence = 0
  const listeners = {}, messages = []
  class Element {
    constructor(text = '', kind = 'button') { this.textContent = text; this.kind = kind }
    closest(selector) { return selector.includes(this.kind) ? this : null }
    getAttribute() { return null }
  }
  const document = {
    hidden: false, documentElement: {}, body: { innerText: 'Accepted 5.4M' },
    querySelector(selector) { return selector.includes('submission-result') ? verdict : null },
    querySelectorAll() { return [] },
    addEventListener(event, callback) { listeners[event] = callback },
  }
  const location = { pathname: '/problems/two-sum/', href: 'https://leetcode.com/problems/two-sum/' }
  runInNewContext(source, {
    document, location, Element, Date: { now: () => now },
    crypto: { randomUUID: () => `event-${++sequence}` },
    chrome: { runtime: { sendMessage(message) { messages.push(message); return send(message) } } },
    MutationObserver: class { constructor(callback) { observe = callback } observe() {} },
    setInterval(callback) { tick = callback },
  })
  return {
    messages,
    at(ms) { now = ms },
    mutate(text) { if (text !== undefined) verdict = new Element(text); observe() },
    submit(text = 'Submit', trusted = true) { listeners.click({ isTrusted: trusted, target: new Element(text) }) },
    key(key = 'a', modifiers = {}) { listeners.keydown({ isTrusted: true, target: new Element('', '.monaco-editor'), key, ...modifiers }) },
    hide(hidden) { document.hidden = hidden; listeners.visibilitychange() },
    navigate(slug) { location.pathname = `/problems/${slug}/`; location.href = `https://leetcode.com${location.pathname}` },
    tick() { tick() },
  }
}

test('page text and old accepted results cannot capture without a new submission', () => {
  const p = page()
  p.mutate()
  p.mutate('Accepted')
  p.submit()
  p.mutate()
  p.mutate('Accepted')
  assert.equal(p.messages.length, 0)
  p.mutate('Pending')
  p.mutate('Accepted')
  assert.equal(p.messages.length, 1)
  assert.equal(p.messages[0].payload.num_submissions, 1)
})

test('submit shortcut captures once, not on failed or unrelated verdicts', () => {
  const p = page()
  p.key('Enter', { ctrlKey: true })
  p.mutate('Not Accepted')
  p.mutate('Wrong Answer')
  p.mutate('Accepted')
  assert.equal(p.messages.length, 0)
  p.key('Enter', { metaKey: true })
  p.mutate('Pending')
  p.mutate('Accepted')
  p.mutate('Accepted')
  assert.equal(p.messages.length, 1)
  assert.equal(p.messages[0].payload.num_submissions, 2)
})

test('untrusted events and unrelated submit buttons do not arm capture', () => {
  const p = page()
  p.submit('Submit feedback')
  p.mutate('Accepted')
  p.submit('Submit', false)
  p.mutate('Pending'); p.mutate('Accepted')
  assert.equal(p.messages.length, 0)
})

test('a rejected worker message can retry with the same event ID', async () => {
  let attempts = 0
  const p = page(async () => {
    if (++attempts === 1) throw new Error('Worker unavailable')
    return { ok: true }
  })
  p.submit(); p.mutate('Accepted')
  await new Promise(setImmediate)
  p.at(5000); p.tick()
  await new Promise(setImmediate)
  assert.equal(p.messages.length, 2)
  assert.equal(p.messages[0].payload.client_event_id, p.messages[1].payload.client_event_id)
  p.at(90000); p.tick()
  assert.equal(p.messages.length, 2)
})

test('failed delivery retries the frozen payload and event ID, never while in flight', async () => {
  let complete
  const p = page(() => new Promise((resolve) => { complete = resolve }))
  p.submit(); p.mutate('Accepted')
  p.at(10000); p.tick()
  assert.equal(p.messages.length, 1)
  complete({ ok: false })
  await new Promise(setImmediate)
  p.at(15000); p.tick()
  assert.equal(p.messages.length, 2)
  assert.equal(p.messages[0].payload, p.messages[1].payload)
  complete({ ok: true })
  await new Promise(setImmediate)
  p.at(90000); p.tick()
  assert.equal(p.messages.length, 2)
})

test('hidden time is excluded from the correct understanding and writing phases', () => {
  const p = page()
  p.at(5000); p.hide(true)
  p.at(105000); p.hide(false)
  p.at(110000); p.key()
  p.at(120000); p.hide(true)
  p.at(220000); p.hide(false)
  p.at(230000); p.submit(); p.mutate('Accepted')
  assert.equal(p.messages[0].payload.time_to_understand_s, 10)
  assert.equal(p.messages[0].payload.time_to_write_s, 20)
})

test('navigation resets attempts before a new page mutation or stale delivery response', async () => {
  let complete
  const p = page(() => new Promise((resolve) => { complete = resolve }))
  p.submit(); p.mutate('Accepted')
  p.navigate('three-sum'); p.mutate('Accepted')
  complete({ ok: true }); await new Promise(setImmediate)
  p.submit(); p.mutate('Pending'); p.mutate('Accepted')
  assert.equal(p.messages.length, 2)
  assert.equal(p.messages[1].payload.slug, 'three-sum')
  assert.notEqual(p.messages[1].payload.client_event_id, p.messages[0].payload.client_event_id)
})
