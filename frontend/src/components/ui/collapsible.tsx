import * as CollapsiblePrimitive from "@radix-ui/react-collapsible"
import clsx from "clsx"
import { forwardRef } from "react"

const Collapsible = CollapsiblePrimitive.Root

const CollapsibleTrigger = CollapsiblePrimitive.Trigger

const CollapsibleContent = forwardRef<
  React.ElementRef<typeof CollapsiblePrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof CollapsiblePrimitive.Content>
>(({ className, ...props }, ref) => (
  <CollapsiblePrimitive.Content
    ref={ref}
    className={clsx(
      "w-full data-[state=open]:w-full",
      className
    )}
    {...props}
  />
))
CollapsibleContent.displayName = "CollapsibleContent"

export {
  Collapsible,
  CollapsibleTrigger,
  CollapsibleContent,
}