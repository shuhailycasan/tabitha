// CSV/TSV parsing for the viewer. RFC-4180-ish: quoted fields, "" escapes, \r\n or \n.

export function parseCSV(text, delimiter = ',') {
  const out = []
  let row = [], field = '', quoted = false
  for (let i = 0; i < text.length; i++) {
    const c = text[i]
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') { field += '"'; i++ }
      else if (c === '"') quoted = false
      else field += c
    } else if (c === '"') quoted = true
    else if (c === delimiter) { row.push(field); field = '' }
    else if (c === '\n') { row.push(field.replace(/\r$/, '')); out.push(row); row = []; field = '' }
    else field += c
  }
  row.push(field.replace(/\r$/, ''))
  if (row.some(v => v !== '')) out.push(row)
  return out
}
