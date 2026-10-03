import * as React from "react"
import { cn } from "@/lib/utils"

const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.ComponentProps<"textarea"> & { glass?: boolean }
>(({ className, glass = false, ...props }, ref) => {
  return (
    <textarea
      className={cn(
        "flex min-h-[80px] w-full rounded-md border px-3 py-2 text-base ring-offset-background placeholder:text-cyan-200/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500/50 focus-visible:ring-offset-2 focus-visible:ring-offset-cyan-950 disabled:cursor-not-allowed disabled:opacity-50 md:text-sm transition-all duration-200",
        glass 
          ? "glass border-cyan-500/20 bg-black/20 text-cyan-100 placeholder:text-cyan-200/30 focus:border-cyan-500/50 focus:bg-black/30" 
          : "border-cyan-500/20 bg-black/20 text-cyan-100 placeholder:text-cyan-200/30 focus:border-cyan-500/50 focus:bg-black/30",
        className
      )}
      ref={ref}
      {...props}
    />
  )
})
Textarea.displayName = "Textarea"

export { Textarea }
