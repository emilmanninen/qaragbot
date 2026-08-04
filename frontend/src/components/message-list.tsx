import type { Message } from "@/lib/types";
import { MessageBubble } from "@/components/message-bubble";
import { LoadingIndicator } from "@/components/loading-indicator";

// Client-side only, always shown — deliberately not part of `messages`
// state, so it's never included when page.tsx builds `history` for the
// backend regardless of how many real turns follow it.
const WELCOME_MESSAGE: Message = {
  role: "assistant",
  content:
    "Hei! Voit kysyä minulta Kelan korkeakouluajan tuista, kuten opintorahasta ja opintolainasta. Huom: tämä on demoprojekti ilmaisella hostauksella, joten ensimmäinen vastaus voi kestää noin 30 sekuntia palvelimen herätessä.",
};

export function MessageList({
  messages,
  isLoading,
}: {
  messages: Message[];
  isLoading?: boolean;
}) {
  return (
    <div className="flex flex-1 flex-col gap-3 overflow-y-auto py-4">
      <MessageBubble message={WELCOME_MESSAGE} />
      {messages.map((message, i) => (
        <MessageBubble key={i} message={message} />
      ))}
      {isLoading && <LoadingIndicator />}
    </div>
  );
}
