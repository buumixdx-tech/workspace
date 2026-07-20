import * as React from "react"
import { ChevronDown, Search, X } from "lucide-react"
import { cn } from "@/lib/utils"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"

export interface PointOption {
  id: number
  name: string
  owner_name?: string
  owner_type?: string
  type: string
}

interface PointSelectProps {
  value: string
  onValueChange: (value: string) => void
  options: PointOption[]
  placeholder?: string
  className?: string
  disabled?: boolean
}

export function PointSelect({
  value,
  onValueChange,
  options,
  placeholder = "选择点位",
  className,
  disabled,
}: PointSelectProps) {
  const [open, setOpen] = React.useState(false)
  const [search, setSearch] = React.useState("")

  const selectedOption = options.find(p => String(p.id) === value)

  const filteredOptions = React.useMemo(() => {
    if (!search.trim()) return options
    const kw = search.toLowerCase()
    return options.filter(p =>
      p.name.toLowerCase().includes(kw) ||
      p.owner_name?.toLowerCase().includes(kw) ||
      p.type.toLowerCase().includes(kw)
    )
  }, [options, search])

  const handleSelect = (id: string) => {
    onValueChange(id)
    setOpen(false)
    setSearch("")
  }

  // When disabled, we still want to show the selected value even if it's not in the options list
  const displayText = selectedOption ? selectedOption.name : (value ? `点位ID: ${value}` : placeholder)

  return (
    <Popover open={open && !disabled} onOpenChange={(o) => { !disabled && setOpen(o); if (!o) setSearch("") }}>
      <PopoverTrigger asChild>
        <button
          type="button"
          disabled={disabled}
          className={cn(
            "flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
            className
          )}
        >
          <span className={cn("truncate flex-1 text-left", !selectedOption && value && "text-foreground")}>
            {displayText}
          </span>
          {!disabled && <ChevronDown className="h-4 w-4 opacity-50" />}
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-96 p-0" align="start">
        <div className="p-2 space-y-2">
          {/* 搜索输入框 */}
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="搜索点位名称、归属、类型..."
              className="w-full h-9 pl-9 pr-8 rounded-md border border-input bg-background text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
            {search && (
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); setSearch("") }}
                className="absolute right-2 top-2.5 text-muted-foreground hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>

          {/* 统计信息 */}
          <div className="text-xs text-muted-foreground px-1">
            {search ? (
              filteredOptions.length === 0 ? "无匹配结果" : `匹配 ${filteredOptions.length} 个`
            ) : (
              selectedOption ? `已选: ${selectedOption.name}` : `共 ${options.length} 个`
            )}
          </div>

          {/* 选项列表 */}
          <div className="max-h-[280px] overflow-y-auto space-y-1 p-1">
            {filteredOptions.length === 0 ? (
              <div className="py-6 text-center text-sm text-muted-foreground">无匹配点位</div>
            ) : (
              filteredOptions.map(p => (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => handleSelect(String(p.id))}
                  className={cn(
                    "w-full text-left px-3 py-2 rounded-md text-sm transition-colors",
                    "hover:bg-accent hover:text-accent-foreground",
                    String(p.id) === value && "bg-accent"
                  )}
                >
                  <div className="font-medium">{p.name}</div>
                  <div className="text-xs text-muted-foreground mt-0.5">
                    {p.owner_name || '闪饮'}{!p.owner_type ? '(自己)' : `(${p.owner_type})`} | {p.type}
                  </div>
                </button>
              ))
            )}
          </div>
        </div>
      </PopoverContent>
    </Popover>
  )
}
