import * as React from "react"
import { cn } from "@/lib/utils"

const Input = React.forwardRef<HTMLInputElement, React.ComponentProps<"input"> & { glass?: boolean }>(
  ({ className, type, glass = false, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(
          "flex h-10 w-full rounded-md border px-3 py-2 text-base ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground placeholder:text-cyan-200/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500/50 focus-visible:ring-offset-2 focus-visible:ring-offset-cyan-950 disabled:cursor-not-allowed disabled:opacity-50 md:text-sm transition-all duration-200",
          glass 
            ? "glass border-cyan-500/20 bg-black/20 text-cyan-100 placeholder:text-cyan-200/30 focus:border-cyan-500/50 focus:bg-black/30" 
            : "border-cyan-500/20 bg-black/20 text-cyan-100 placeholder:text-cyan-200/30 focus:border-cyan-500/50 focus:bg-black/30",
          className
        )}
        ref={ref}
        {...props}
      />
    )
  }
)
Input.displayName = "Input"

export { Input }
