// Zero-dependency .xlsx reader: unzips via DecompressionStream, parses sheet XML with DOMParser.
// View-only: reads cell values (shared strings, inline strings, numbers as text). No styles, no dates.

function colIndex(ref) {
  let n = 0
  for (const c of ref.match(/[A-Z]+/i)?.[0] || 'A') n = n * 26 + c.toUpperCase().charCodeAt(0) - 64
  return n - 1
}

function descendantsText(el, tag) {
  return Array.from(el.getElementsByTagNameNS('*', tag)).map(x => x.textContent || '').join('')
}

export async function parseXlsx(file) {
  if (!('DecompressionStream' in window)) {
    throw new Error('This browser cannot open compressed Excel workbooks. Try exporting the sheet as CSV.')
  }
  const bytes = new Uint8Array(await file.arrayBuffer())
  const view = new DataView(bytes.buffer)

  // locate end-of-central-directory record, then walk the central directory
  let eocd = -1
  for (let p = bytes.length - 22; p >= Math.max(0, bytes.length - 65558); p--) {
    if (view.getUint32(p, true) === 0x06054b50) { eocd = p; break }
  }
  if (eocd < 0) throw new Error('That does not look like a valid .xlsx workbook.')

  const count = view.getUint16(eocd + 10, true)
  const cdOffset = view.getUint32(eocd + 16, true)
  const entries = new Map()
  let p = cdOffset
  for (let i = 0; i < count; i++) {
    if (view.getUint32(p, true) !== 0x02014b50) break
    const method = view.getUint16(p + 10, true)
    const compressed = view.getUint32(p + 20, true)
    const nameLen = view.getUint16(p + 28, true)
    const extraLen = view.getUint16(p + 30, true)
    const commentLen = view.getUint16(p + 32, true)
    const local = view.getUint32(p + 42, true)
    const name = new TextDecoder().decode(bytes.subarray(p + 46, p + 46 + nameLen))
    entries.set(name, { method, compressed, local })
    p += 46 + nameLen + extraLen + commentLen
  }

  async function read(name) {
    const e = entries.get(name)
    if (!e) return null
    const nlen = view.getUint16(e.local + 26, true)
    const elen = view.getUint16(e.local + 28, true)
    const start = e.local + 30 + nlen + elen
    const part = bytes.slice(start, start + e.compressed)
    if (e.method === 0) return new TextDecoder().decode(part)
    if (e.method !== 8) throw new Error('This workbook uses an unsupported compression format.')
    const stream = new Blob([part]).stream().pipeThrough(new DecompressionStream('deflate-raw'))
    return await new Response(stream).text()
  }

  const parser = new DOMParser()
  const xml = async name => {
    const t = await read(name)
    if (!t) return null
    const doc = parser.parseFromString(t, 'application/xml')
    if (doc.querySelector('parsererror')) throw new Error('Could not read part of this workbook.')
    return doc
  }

  const wb = await xml('xl/workbook.xml')
  const rels = await xml('xl/_rels/workbook.xml.rels')
  if (!wb || !rels) throw new Error('Could not find workbook sheets.')

  const relation = new Map(
    Array.from(rels.getElementsByTagNameNS('*', 'Relationship'))
      .map(r => [r.getAttribute('Id'), r.getAttribute('Target')])
  )

  let shared = []
  const ss = await xml('xl/sharedStrings.xml')
  if (ss) shared = Array.from(ss.getElementsByTagNameNS('*', 'si')).map(si => descendantsText(si, 't'))

  const sheets = []
  for (const sh of Array.from(wb.getElementsByTagNameNS('*', 'sheet'))) {
    const target = relation.get(sh.getAttribute('r:id'))
    if (!target) continue
    const path = target.startsWith('/') ? target.slice(1) : 'xl/' + target.replace(/^\.\//, '')
    const doc = await xml(path)
    if (!doc) continue
    const rows = []
    for (const rowEl of Array.from(doc.getElementsByTagNameNS('*', 'row'))) {
      const row = []
      for (const c of Array.from(rowEl.getElementsByTagNameNS('*', 'c'))) {
        const idx = colIndex(c.getAttribute('r') || 'A1')
        const type = c.getAttribute('t')
        const v = c.getElementsByTagNameNS('*', 'v')[0]
        const inline = c.getElementsByTagNameNS('*', 'is')[0]
        let val = ''
        if (type === 's' && v) val = shared[Number(v.textContent)] ?? ''
        else if (type === 'inlineStr' && inline) val = descendantsText(inline, 't')
        else if (v) val = v.textContent
        while (row.length <= idx) row.push('')
        row[idx] = val
      }
      rows.push(row)
    }
    sheets.push({ name: sh.getAttribute('name') || 'Sheet', rows })
  }
  if (!sheets.length) throw new Error('This workbook has no readable sheets.')
  return sheets
}
