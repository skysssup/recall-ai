const { test, afterEach, mock } = require('node:test')
const assert = require('node:assert/strict')
const { readFileSync } = require('node:fs')
const ts = require('typescript')
const { JSDOM } = require('jsdom')

for (const extension of ['.ts', '.tsx']) {
  require.extensions[extension] = (module, filename) => {
    const { outputText } = ts.transpileModule(readFileSync(filename, 'utf8'), {
      fileName: filename,
      compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
    })
    module._compile(outputText, filename)
  }
}

const dom = new JSDOM('<div id="root"></div>', { url: 'http://localhost:5173' })
for (const key of ['window', 'document', 'Element', 'HTMLElement', 'HTMLInputElement', 'HTMLTextAreaElement', 'MouseEvent', 'KeyboardEvent', 'Event', 'localStorage']) {
  globalThis[key] = dom.window[key]
}
globalThis.IS_REACT_ACT_ENVIRONMENT = true
const { createElement: h, act } = require('react')
const { createRoot } = require('react-dom/client')
const { MemoryRouter, Routes, Route } = require('react-router-dom')
const Review = require('../src/pages/Review.tsx').default
const Analytics = require('../src/pages/Analytics.tsx').default
const Problems = require('../src/pages/Problems.tsx').default
const Graph = require('../src/pages/Graph.tsx').default
const Settings = require('../src/pages/Settings.tsx').default
const LogSolve = require('../src/pages/LogSolve.tsx').default
const Layout = require('../src/components/Layout.tsx').default
let root
const card = { id: 'card', title: 'Two Sum', difficulty: 'Easy', platform: 'leetcode', slug: 'two-sum', review_count: 0, lapses: 0, retrievability: 1, notes: '' }

function serve(review = async () => Response.json({})) {
  mock.method(globalThis, 'fetch', async (url, init) => {
    if (url === '/api/problems/card/reviews') return review(init)
    if (url.startsWith('/api/reviews/queue')) return Response.json([card])
    if (url.startsWith('/api/reviews/preview')) return Response.json({ intervals_days: { 1: 0.5, 2: 1, 3: 2, 4: 6 } })
    if (url === '/api/settings') return Response.json({ daily_goal: 10, api_token_hint: '' })
    if (url === '/api/topics') return Response.json([])
    if (url.startsWith('/api/problems')) return Response.json([card])
    if (url === '/api/dashboard') return Response.json({ reviews_today: 0 })
    if (url.startsWith('/api/search')) return Response.json([{ kind: 'problem', id: 'card', title: 'Two Sum', subtitle: 'Easy' }])
    throw new Error(`Unexpected request: ${url}`)
  })
}

async function render(component) {
  root = createRoot(document.getElementById('root'))
  await act(async () => root.render(h(MemoryRouter, null, h(component))))
}

async function click(element) {
  await act(async () => element.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true })))
}

function button(text) {
  return [...document.querySelectorAll('button')].find((b) => b.textContent.includes(text))
}

afterEach(async () => {
  if (root) await act(async () => root.unmount())
  root = null
  mock.restoreAll()
  localStorage.clear()
})

test('rating clicks and keyboard shortcuts share an in-flight guard', async () => {
  let resolve, calls = 0
  serve(() => { calls++; return new Promise((done) => { resolve = done }) })
  await render(Review)
  await act(async () => {
    button('Good').click()
    button('Good').click()
    window.dispatchEvent(new KeyboardEvent('keydown', { key: '3' }))
  })
  assert.equal(calls, 1)
  assert.ok([...document.querySelectorAll('.rating-btn')].every((b) => b.disabled))
  await act(async () => resolve(Response.json({})))
  assert.match(document.body.textContent, /Queue clear/)
})

test('a failed rating keeps the card, displays the error, and permits retry', async () => {
  let fail = true
  serve(async () => {
    if (fail) throw new Error('Backend offline')
    return Response.json({})
  })
  await render(Review)
  await click(button('Good'))
  assert.match(document.querySelector('[role="alert"]').textContent, /Backend offline/)
  assert.match(document.querySelector('.review-card').textContent, /Two Sum/)
  assert.equal(button('Good').disabled, false)
  fail = false
  await click(button('Good'))
  assert.match(document.body.textContent, /Queue clear/)
})

test('a successful review refreshes the mounted sidebar progress', async () => {
  let reviews = 0
  serve(async () => { reviews++; return Response.json({}) })
  const fetch = globalThis.fetch
  mock.method(globalThis, 'fetch', async (url, init) => url === '/api/dashboard' ? Response.json({ reviews_today: reviews }) : fetch(url, init))
  await render(() => h(Routes, null, h(Route, { element: h(Layout) }, h(Route, { index: true, element: h(Review) }))))
  assert.equal(document.querySelector('.sidebar-foot strong').textContent, '0/10')
  await click(button('Good'))
  assert.equal(document.querySelector('.sidebar-foot strong').textContent, '1/10')
})

for (const [name, component] of [['Analytics', Analytics], ['Problems', Problems], ['Graph', Graph]]) {
  test(`${name} reports an authentication failure instead of loading or empty data`, async () => {
    mock.method(globalThis, 'fetch', async () => Response.json({ detail: 'Invalid API token' }, { status: 401 }))
    await render(component)
    assert.match(document.querySelector('[role="alert"]').textContent, /Invalid API token/)
    assert.doesNotMatch(document.body.textContent, /Loading|No problems yet/)
  })
}

test('problem save and delete failures preserve the visible data and form', async () => {
  serve()
  const fetch = globalThis.fetch
  mock.method(globalThis, 'fetch', async (url, init) => {
    if (init?.method === 'DELETE') return Response.json({ detail: 'Delete failed' }, { status: 500 })
    if (init?.method === 'POST') return Response.json({ detail: 'Duplicate problem' }, { status: 409 })
    return fetch(url, init)
  })
  await render(Problems)
  await click(button('Delete'))
  assert.match(document.querySelector('[role="alert"]').textContent, /Delete failed/)
  assert.match(document.querySelector('tbody').textContent, /Two Sum/)
  await click(button('Add problem'))
  await act(async () => document.querySelector('form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })))
  assert.match(document.querySelector('[role="alert"]').textContent, /Duplicate problem/)
  assert.ok(document.querySelector('form'))
})

for (const [name, component] of [['Settings', Settings], ['Problems', Problems], ['Log Solve', LogSolve]]) {
  test(`${name} associates each visible form field with a label`, async () => {
    serve()
    await render(component)
    if (component === Problems) await click(button('Add problem'))
    const fields = [...document.querySelectorAll('input:not([hidden]), select, textarea')]
    assert.ok(fields.length > 0)
    for (const field of fields) assert.ok(field.labels.length || field.getAttribute('aria-label'), `${field.id || field.tagName} lacks a name`)
  })
}

test('extension popup labels are associated with their inputs', () => {
  const popup = new JSDOM(readFileSync(`${__dirname}/../../extension/popup.html`, 'utf8'))
  for (const input of popup.window.document.querySelectorAll('input')) assert.equal(input.labels.length, 1)
  popup.window.close()
})

test('search results are keyboard-focusable links', async () => {
  serve()
  await render(Layout)
  await act(async () => window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', ctrlKey: true })))
  const input = document.querySelector('.search-pop input')
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, 'sum')
    input.dispatchEvent(new Event('input', { bubbles: true }))
  })
  await act(async () => new Promise((resolve) => setTimeout(resolve, 150)))
  const link = document.querySelector('.search-hit')
  assert.equal(link.tagName, 'A')
  assert.equal(link.tabIndex, 0)
  assert.equal(link.getAttribute('href'), '/problems?focus=card')
})
