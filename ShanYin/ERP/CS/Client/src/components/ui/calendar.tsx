import * as React from "react"
import { DayPicker, DayPickerProps } from "react-day-picker"
import { cn } from "@/lib/utils"

export type CalendarProps = DayPickerProps

function Calendar({
  className,
  classNames,
  showOutsideDays = true,
  ...props
}: CalendarProps) {
  return (
    <DayPicker
      showOutsideDays={showOutsideDays}
      className={cn("p-3", className)}
      classNames={classNames}
      {...props}
    />
  )
}
Calendar.displayName = "Calendar"

export { Calendar }
