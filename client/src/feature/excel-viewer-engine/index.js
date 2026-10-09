// excel-viewer-engine — tiny view-only spreadsheet reader for the Tabitha desktop.
// No dependencies. Turn a File into { name, sheets: [{ name, rows: string[][] }] }.

import { parseCSV } from './csv.js'
import { parseXlsx } from './xlsx.js'

export const MAX_FILE_BYTES = 20 * 1024 * 1024
export const ACCEPTED_EXTENSIONS = ['xlsx', 'csv', 'tsv']

export async function parseWorkbook(file) {
  if (file.size > MAX_FILE_BYTES) throw new Error('Please choose a file under 20 MB.')
  const ext = file.name.split('.').pop().toLowerCase()
  if (ext === 'csv' || ext === 'tsv') {
    const rows = parseCSV(await file.text(), ext === 'tsv' ? '\t' : ',')
    return { name: file.name, sheets: [{ name: 'Sheet 1', rows }] }
  }
  if (ext === 'xlsx') return { name: file.name, sheets: await parseXlsx(file) }
  throw new Error('Choose an .xlsx, .csv, or .tsv file.')
}

// 0 -> A, 25 -> Z, 26 -> AA …
export function columnName(n) {
  let s = ''
  for (n++; n; n = Math.floor((n - 1) / 26)) s = String.fromCharCode(65 + (n - 1) % 26) + s
  return s
}

// What the viewer renders: caps rows/cols so giant sheets don't hang the tab.
export function viewSlice(sheet, { maxRows = 250, maxCols = 40 } = {}) {
  const rows = sheet.rows.slice(0, maxRows)
  const cols = Math.min(maxCols, Math.max(1, ...rows.map(r => r.length)))
  return { rows, cols, truncated: sheet.rows.length > maxRows }
}
