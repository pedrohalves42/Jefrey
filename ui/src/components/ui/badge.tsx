import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:ring-offset-2",
  {
    variants: {
      variant: {
        default: "border-cyan-500/30 bg-cyan-500/10 text-cyan-300 hover:bg-cyan-500/20 hover:border-cyan-500/50",
        secondary: "border-slate-500/30 bg-slate-500/10 text-slate-300 hover:bg-slate-500/20",
        destructive: "border-red-500/30 bg-red-500/10 text-red-300 hover:bg-red-500/20",
        outline: "border-cyan-500/30 text-cyan-300 hover:bg-cyan-500/10",
        success: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20",
        glass: "glass text-cyan-200",
      },
    },
    defaultVariants: { variant: "default" },
  }
)

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) { 
  return <div className={cn(badgeVariants({ variant }), className)} {...props} /> 
}

export { Badge, badgeVariants }
