import * as React from "react"
import * as Popover from "@radix-ui/react-popover"
import { cn } from "@/lib/utils"

interface DatePickerProps {
  value?: string
  onChange: (value: string) => void
  placeholder?: string
  className?: string
}

const WEEKDAYS = ["日", "一", "二", "三", "四", "五", "六"]

function getDaysInMonth(year: number, month: number) {
  return new Date(year, month + 1, 0).getDate()
}

function toDate(value: string | undefined) {
  if (!value) return null
  const d = new Date(value)
  return isNaN(d.getTime()) ? null : d
}

export function DatePicker({ value, onChange, placeholder = "选择日期", className }: DatePickerProps) {
  const today = new Date()
  const [open, setOpen] = React.useState(false)

  const current = toDate(value) || today
  const [viewYear, setViewYear] = React.useState(current.getFullYear())
  const [viewMonth, setViewMonth] = React.useState(current.getMonth())

  React.useEffect(() => {
    if (value) {
      const d = toDate(value)
      if (d) {
        setViewYear(d.getFullYear())
        setViewMonth(d.getMonth())
      }
    }
  }, [value])

  const daysInView = getDaysInMonth(viewYear, viewMonth)
  const firstDayOfWeek = new Date(viewYear, viewMonth, 1).getDay()

  const cells: (number | null)[] = []
  for (let i = 0; i < firstDayOfWeek; i++) cells.push(null)
  for (let d = 1; d <= daysInView; d++) cells.push(d)

  const selectDay = (day: number) => {
    const y = viewYear
    const m = String(viewMonth + 1).padStart(2, "0")
    const dStr = String(day).padStart(2, "0")
    onChange(`${y}-${m}-${dStr}`)
    setOpen(false)
  }

  const selectedDay = value ? toDate(value)?.getDate() : null
  const isSelectedMonth = value
    ? toDate(value)?.getFullYear() === viewYear && toDate(value)?.getMonth() === viewMonth
    : false

  const prevMonth = () => {
    if (viewMonth === 0) { setViewYear(y => y - 1); setViewMonth(11); }
    else setViewMonth(m => m - 1)
  }
  const nextMonth = () => {
    if (viewMonth === 11) { setViewYear(y => y + 1); setViewMonth(0); }
    else setViewMonth(m => m + 1)
  }

  const years = Array.from({ length: 10 }, (_, i) => today.getFullYear() - 5 + i)
  const months = ["1月","2月","3月","4月","5月","6月","7月","8月","9月","10月","11月","12月"]

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <input
          readOnly
          className={cn(
            "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 cursor-pointer",
            className
          )}
          placeholder={placeholder}
          value={value || ""}
        />
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          className="z-50 bg-white rounded-md border border-gray-200 shadow-md p-3 w-64 text-gray-900"
          sideOffset={4}
          onOpenAutoFocus={e => e.preventDefault()}
        >
          <div className="flex items-center justify-between mb-2">
            <button type="button" onClick={prevMonth} className="p-1 hover:bg-gray-100 rounded text-sm text-gray-700">‹</button>
            <div className="flex gap-1">
              <select
                className="text-sm border rounded px-1 py-0.5 text-gray-700"
                value={viewMonth}
                onChange={e => setViewMonth(Number(e.target.value))}
              >
                {months.map((m, i) => <option key={i} value={i}>{m}</option>)}
              </select>
              <select
                className="text-sm border rounded px-1 py-0.5 text-gray-700"
                value={viewYear}
                onChange={e => setViewYear(Number(e.target.value))}
              >
                {years.map(y => <option key={y} value={y}>{y}年</option>)}
              </select>
            </div>
            <button type="button" onClick={nextMonth} className="p-1 hover:bg-gray-100 rounded text-sm text-gray-700">›</button>
          </div>
          <div className="grid grid-cols-7 gap-0.5 text-center text-xs text-gray-400 mb-1">
            {WEEKDAYS.map(d => <div key={d}>{d}</div>)}
          </div>
          <div className="grid grid-cols-7 gap-0.5">
            {cells.map((day, idx) => {
              if (day === null) return <div key={`empty-${idx}`} />
              const isSelected = isSelectedMonth && day === selectedDay
              const isToday = day === today.getDate()
                && viewYear === today.getFullYear()
                && viewMonth === today.getMonth()
              return (
                <button
                  key={day}
                  type="button"
                  onClick={() => selectDay(day)}
                  className={cn(
                    "h-7 w-7 text-sm text-gray-900 rounded hover:bg-gray-100",
                    isSelected && "bg-blue-500 text-white hover:bg-blue-600",
                    isToday && !isSelected && "border border-blue-400"
                  )}
                >
                  {day}
                </button>
              )
            })}
          </div>
          <div className="mt-2 pt-2 border-t flex justify-end">
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="text-xs text-gray-400 hover:text-gray-700 px-2 py-1"
            >
              取消
            </button>
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  )
}
