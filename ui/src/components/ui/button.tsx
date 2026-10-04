import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center rounded-md text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500/50 focus-visible:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none",
  {
    variants: {
      variant: {
        default: "bg-cyan-600 text-white hover:bg-cyan-500 shadow-[0_0_12px_rgba(6,182,212,0.4)] hover:shadow-[0_0_20px_rgba(6,182,212,0.6)]",
        destructive: "bg-red-600 text-white hover:bg-red-500 shadow-[0_0_12px_rgba(220,38,38,0.4)]",
        outline: "border border-cyan-500/30 bg-transparent hover:bg-cyan-500/10 hover:border-cyan-500/50",
        secondary: "bg-slate-700 text-white hover:bg-slate-600 shadow-[0_0_8px_rgba(0,0,0,0.3)]",
        ghost: "hover:bg-cyan-500/10 hover:text-cyan-300",
        link: "text-cyan-400 underline-offset-4 hover:underline",
        glass: "glass hover:bg-cyan-500/20 text-cyan-100 hover:text-white",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 rounded-md px-3",
        lg: "h-11 rounded-md px-8",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: { variant: "default", size: "default" }
  }
)

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(({ className, variant, size, ...props }, ref) => (
  <button className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />
))
Button.displayName = "Button"

export { buttonVariants }
