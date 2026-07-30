import type { Message } from "@/lib/types";
import { MessageBubble } from "@/components/message-bubble";

export function MessageList({ messages }: { messages: Message[] }) {
  return (
    <div className="flex flex-1 flex-col gap-3 overflow-y-auto py-4">
      {messages.map((message, i) => (
        <MessageBubble key={i} message={message} />
      ))}
    </div>
  );
}
