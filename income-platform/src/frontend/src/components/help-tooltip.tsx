"use client";

import { HelpCircle } from "lucide-react";
import { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider } from "@/components/ui/tooltip";

interface HelpTooltipProps {
  text: string;
  side?: "top" | "bottom" | "left" | "right";
}

export function HelpTooltip({ text, side = "top" }: HelpTooltipProps) {
  return (
    <TooltipProvider delay={200}>
      <Tooltip>
        <TooltipTrigger
          render={
            <button
              type="button"
              onClick={(e) => e.stopPropagation()}
              className="inline-flex shrink-0 text-muted-foreground/40 hover:text-muted-foreground/80 transition-colors ml-1 align-middle focus:outline-none"
              aria-label="Help"
            />
          }
        >
          <HelpCircle className="h-3 w-3" />
        </TooltipTrigger>
        <TooltipContent side={side} className="max-w-65 text-xs leading-relaxed">
          {text}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

// Convenience wrapper for table column headers
export function ColHeader({ label, helpKey, helpMap }: {
  label: string;
  helpKey: string;
  helpMap: Record<string, string>;
}) {
  const text = helpMap[helpKey];
  return (
    <span className="inline-flex items-center gap-0.5">
      {label}
      {text && <HelpTooltip text={text} />}
    </span>
  );
}
