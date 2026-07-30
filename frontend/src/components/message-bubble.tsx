import type { Message } from "@/lib/types";
import { CitationBadge } from "@/components/citation-badge";

// Splits on "[1]"-style markers, keeping them in the array, so each can be
// swapped for a CitationBadge while everything else stays plain text.
function renderContent(content: string, citations?: Message["citations"]) {
  if (!citations) return content;

  return content.split(/(\[\d+\])/g).map((part, i) => {
    const match = part.match(/^\[(\d+)\]$/);
    const citation = match && citations[match[1]];
    return citation ? (
      <CitationBadge key={i} index={Number(match[1])} citation={citation} />
    ) : (
      part
    );
  });
}

export function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] rounded-lg px-4 py-2 text-sm whitespace-pre-wrap ${
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-muted text-foreground"
        }`}
      >
        {renderContent(message.content, message.citations)}
      </div>
    </div>
  );
}
