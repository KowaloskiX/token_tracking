"use client";

import * as React from "react";
import * as SliderPrimitive from "@radix-ui/react-slider";
import { cn } from "@/lib/utils";

const Slider = React.forwardRef<
  React.ElementRef<typeof SliderPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof SliderPrimitive.Root>
>(({ className, ...props }, ref) => (
  <SliderPrimitive.Root
    ref={ref}
    className={cn("relative flex items-center select-none touch-none w-full", className)}
    {...props}
  >
    <SliderPrimitive.Track className="bg-muted relative flex-1 rounded-full h-2">
      <SliderPrimitive.Range className="absolute bg-primary rounded-full h-full" />
    </SliderPrimitive.Track>
    <SliderPrimitive.Thumb className="block w-4 h-4 rounded-full bg-background shadow-sm focus:outline-none" />
  </SliderPrimitive.Root>
));

Slider.displayName = SliderPrimitive.Root.displayName;

export { Slider };
