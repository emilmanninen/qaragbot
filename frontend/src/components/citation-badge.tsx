"use client";

import { Badge } from "@/components/ui/badge";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import type { Citation } from "@/lib/types";

export function CitationBadge({
  index,
  citation,
}: {
  index: number;
  citation: Citation;
}) {
  return (
    <Popover>
      <PopoverTrigger
        render={
          <Badge
            variant="secondary"
            render={<button type="button" />}
            className="mx-0.5 -translate-y-0.5 cursor-pointer text-[0.65rem]"
          >
            [{index}]
          </Badge>
        }
      />
      <PopoverContent className="w-80">
        <p className="text-sm">{citation.snippet}</p>
        <a
          href={citation.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary text-xs break-all underline"
        >
          {citation.source_url}
        </a>
      </PopoverContent>
    </Popover>
  );
}
