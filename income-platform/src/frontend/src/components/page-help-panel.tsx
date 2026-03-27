"use client";

import { useState } from "react";
import { HelpCircle } from "lucide-react";
import {
  Sheet,
  SheetTrigger,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import type { PageHelpContent } from "@/lib/page-help-content";

interface PageHelpPanelProps {
  content: PageHelpContent;
}

export function PageHelpPanel({ content }: PageHelpPanelProps) {
  const [open, setOpen] = useState(false);

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger
        render={
          <button
            type="button"
            title="Page help"
            aria-label="Open page help"
            className="p-1.5 text-muted-foreground/50 hover:text-muted-foreground transition-colors rounded focus:outline-none"
          />
        }
      >
        <HelpCircle className="h-4 w-4" />
      </SheetTrigger>

      <SheetContent side="right" className="w-full sm:max-w-[420px] overflow-y-auto p-0">
        <SheetHeader className="px-5 pt-5 pb-3 border-b border-border">
          <div className="flex items-center gap-2">
            <HelpCircle className="h-4 w-4 text-blue-400 shrink-0" />
            <SheetTitle className="text-base font-semibold">{content.pageTitle}</SheetTitle>
          </div>
          <SheetDescription className="text-xs text-muted-foreground mt-1">
            {content.subtitle}
          </SheetDescription>
        </SheetHeader>

        <div className="px-5 py-4 space-y-5">
          {content.sections.map((section, i) => (
            <div key={i}>
              <h3 className="text-xs font-bold uppercase tracking-wider text-blue-400 mb-1.5">
                {section.title}
              </h3>
              <p className="text-sm text-muted-foreground leading-relaxed whitespace-pre-line">
                {section.body}
              </p>
            </div>
          ))}
        </div>

        <div className="px-5 pb-5">
          <div className="border-t border-border pt-3 text-[10px] text-muted-foreground/50 uppercase tracking-wider">
            Income Platform · Context Help
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
