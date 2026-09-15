import { jsx as _jsx } from "react/jsx-runtime";
import * as React from "react";
import { cva } from "class-variance-authority";
import { cn } from "@/lib/utils";
const buttonVariants = cva("inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none disabled:opacity-50 disabled:pointer-events-none", {
    variants: {
        variant: { default: "bg-primary text-primary-foreground hover:bg-primary/90", destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90", outline: "border border-input bg-background hover:bg-accent", secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80", ghost: "hover:bg-accent", link: "text-primary underline-offset-4 hover:underline" },
        size: { default: "h-10 px-4 py-2", sm: "h-9 rounded-md px-3", lg: "h-11 rounded-md px-8", icon: "h-10 w-10" }
    },
    defaultVariants: { variant: "default", size: "default" }
});
export const Button = React.forwardRef(({ className, variant, size, ...props }, ref) => (_jsx("button", { className: cn(buttonVariants({ variant, size, className })), ref: ref, ...props })));
Button.displayName = "Button";
export { buttonVariants };
