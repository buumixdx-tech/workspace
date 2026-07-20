import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"
import ExcelJS from 'exceljs'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(date: Date | string | undefined | null): string {
  if (!date) return '-'
  if (typeof date === 'string' && /^\d{8}$/.test(date)) {
    date = date.substring(0, 4) + '-' + date.substring(4, 6) + '-' + date.substring(6, 8)
  }
  const d = typeof date === 'string' ? new Date(date) : date
  if (isNaN(d.getTime())) return '-'
  return d.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
}

export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('zh-CN', {
    style: 'currency',
    currency: 'CNY',
  }).format(amount)
}

export async function exportToExcel<T>(
  data: T[],
  columns: { key: string; header: string; format?: (value: unknown, row: T) => string }[],
  filename: string
) {
  if (!data.length) return

  const workbook = new ExcelJS.Workbook()
  const worksheet = workbook.addWorksheet('Sheet1')

  // Header row
  const headerRow = worksheet.addRow(columns.map(c => c.header))
  headerRow.eachCell(cell => {
    cell.font = { name: '微软雅黑', bold: true }
    cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFFFFF00' } }
    cell.alignment = { horizontal: 'center', vertical: 'middle', wrapText: true }
  })
  headerRow.height = 24

  // Data rows
  for (const row of data) {
    const rowValues = columns.map(col => {
      const value = (row as Record<string, unknown>)[col.key]
      return col.format ? col.format(value, row) : String(value ?? '')
    })
    const rowNode = worksheet.addRow(rowValues)
    rowNode.eachCell(cell => {
      cell.font = { name: '微软雅黑' }
      cell.alignment = { wrapText: true, vertical: 'top' }
    })
  }

  // Auto-fit column widths based on Chinese chars (width ~2) vs ASCII (width ~1)
  worksheet.columns.forEach(col => {
    let maxLen = 0
    col.eachCell?.(cell => {
      const str = String(cell.value ?? '')
      // Chinese/Full-width chars count as 2, ASCII as 1
      const len = [...str].reduce((acc, ch) => {
        const code = ch.charCodeAt(0)
        return acc + (code > 0xFF ? 2 : 1)
      }, 0)
      if (len > maxLen) maxLen = len
    })
    col.width = Math.min(Math.max(maxLen + 4, 8), 60)
  })

  const buffer = await workbook.xlsx.writeBuffer()
  const blob = new Blob([buffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${filename}.xlsx`
  a.click()
  URL.revokeObjectURL(url)
}
