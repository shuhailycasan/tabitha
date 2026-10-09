// chat commands — pure helpers for `@file` mentions and `/commands` (no Vue state).
// `/commands` run backend tools directly via POST /api/run (no LLM wait); `@file` adds another
// uploaded file to the question's scope (the backend merges them on the shared first column).

export const COMMANDS = [
  { label: '/list', hint: 'rows as a table — /list [sheet] [n]' },
  { label: '/stats', hint: 'stats — /stats, /stats <column>, /stats <sheet> <column>' },
  { label: '/top', hint: 'highest rows — /top <column> [n]' },
  { label: '/bottom', hint: 'lowest rows — /bottom <column> [n]' },
  { label: '/lookup', hint: 'find a name in every sheet — /lookup <name>' },
  { label: '/think', hint: 'turn step-by-step thinking on' },
  { label: '/fast', hint: 'turn thinking off (about 4x quicker)' },
  { label: '/clear', hint: 'clear this chat' },
  { label: '/help', hint: 'show these commands' },
]

export const stem = n => n.replace(/\.[^.]+$/, '')
const same = (a, b) => String(a).toLowerCase() === String(b).toLowerCase()
const quote = s => (/\s/.test(s) ? `"${s}"` : s)
const byMention = (list, name) => list.find(d => same(stem(d.name), name))

// active dataset first, then each @mentioned file
export function scopeIds(text, activeId, list) {
  const ids = activeId ? [activeId] : []
  for (const m of text.matchAll(/@(\S+)/g)) {
    const d = byMention(list, m[1])
    if (d && !ids.includes(d.id)) ids.push(d.id)
  }
  return ids
}

// `@sample_attendance` -> `the file "sample_attendance.xlsx"`: scope, not something to search for
export function cleanMentions(text, list) {
  return text
    .replace(/@(\S+)/g, (m, s) => { const d = byMention(list, s); return d ? `the file "${d.name}"` : m })
    .replace(/\s{2,}/g, ' ').trim()
}

// 2nd-stage suggestions for a command's arguments: real sheet/column names of the files in scope
function argPool(cmd, input, activeId, list) {
  const ds = scopeIds(input, activeId, list).map(i => list.find(d => d.id === i)).filter(Boolean)
  const sheets = ds.flatMap(d => d.sheets.map(s => quote(s.name)))
  const cols = [...new Set(ds.flatMap(d => d.sheets.flatMap(s => s.columns.map(quote))))]
  if (cmd === '/list' || cmd === '/stats') return [...sheets, ...cols]
  if (cmd === '/top' || cmd === '/bottom') return cols
  return []
}

// Popup state for the word under the cursor, or null. A word typed in full yields null so Enter sends.
export function suggest(input, pos, activeId, list) {
  const before = input.slice(0, pos)
  const m = before.match(/(?:^|\s)(\S*)$/)
  if (!m) return null
  const quotes = (before.match(/"/g) || []).length
  if (quotes && quotes % 2 === 0 && before.endsWith('"')) return null // a quoted argument was just closed
  let word = m[1], tokenStart = pos - word.length
  if (quotes % 2) { tokenStart = before.lastIndexOf('"'); word = before.slice(tokenStart) } // inside "multi word" name
  const lw = word.toLowerCase()
  const show = items => {
    const hit = items.filter(it => it.label.toLowerCase().includes(lw))
    return hit.length && !(hit.length === 1 && hit[0].label === word) ? { items: hit, i: 0, tokenStart, pos } : null
  }
  if (word.startsWith('@')) return show(list.map(d => ({ label: '@' + stem(d.name), hint: 'include this file' })))
  const head = before.slice(0, tokenStart).trim()
  if (word.startsWith('/') && !head) return show(COMMANDS)
  if (head.startsWith('/')) {
    const cmd = head.split(/\s+/)[0]
    if (!word && !['/top', '/bottom'].includes(cmd)) return null // optional args: open only once the user types, so Enter still sends
    return show(argPool(cmd, input, activeId, list).map(label => ({ label, hint: 'column / sheet' })))
  }
  return null
}

// "/stats "Days Absent"" -> { ids, tool, args } | { local } | { error }
export function parseCommand(text, activeId, list) {
  const parts = text.match(/"[^"]*"|\S+/g) || []
  const cmd = parts[0]
  const rest = parts.slice(1).filter(p => !p.startsWith('@')).map(p => p.replace(/^"|"$/g, '')) // @file is scope, not an argument
  const local = { '/clear': 'clear', '/fast': 'fast', '/think': 'think', '/help': 'help' }[cmd]
  if (local) return { local }

  const ids = scopeIds(text, activeId, list)
  const ds = ids.map(i => list.find(d => d.id === i)).filter(Boolean)
  const lastSheet = ds[ds.length - 1]?.sheets[0]?.name // the @mentioned file, else the active one
  const isSheet = n => same(n, 'all') || ds.some(d => d.sheets.some(s => same(s.name, n)))
  const sheetOf = col => ds.flatMap(d => d.sheets).find(s => s.columns.some(c => same(c, col)))?.name
  const colSheet = rest[0] ? sheetOf(rest[0]) || lastSheet : lastSheet

  const specs = {
    '/list': () => ({ tool: 'list_rows', args: /^\d+$/.test(rest[0] || '')
      ? { sheet: lastSheet, limit: +rest[0] }
      : { sheet: rest[0] || lastSheet, limit: +rest[1] || 30 } }),
    '/stats': () => ({ tool: 'summarize', args: rest[0] && isSheet(rest[0])
      ? { sheet: rest[0], column: rest[1] }
      : { sheet: colSheet, column: rest[0] } }),
    '/lookup': () => ({ tool: 'lookup', args: { name: rest.join(' ') } }),
    '/top': () => ({ tool: 'top_rows', args: { sheet: colSheet, column: rest[0], n: +rest[1] || 5 } }),
    '/bottom': () => ({ tool: 'top_rows', args: { sheet: colSheet, column: rest[0], n: +rest[1] || 5, ascending: true } }),
  }
  if (!specs[cmd]) return { error: `Unknown command ${cmd} — try /help` }
  if (!ids.length) return { error: 'Pick a file first (or @mention one) before running commands.' }
  const { tool, args } = specs[cmd]()
  for (const k of Object.keys(args)) if (args[k] === undefined) delete args[k]
  return { ids, tool, args }
}
