"use client";

import { useState } from "react";
import { ChatInput } from "@/components/chat-input";
import { MessageList } from "@/components/message-list";
import type { Message, QueryError } from "@/lib/types";

type Status = "idle" | "loading" | "error";

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<QueryError | null>(null);

  async function handleSubmit(question: string) {
    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setStatus("loading");
    setError(null);

    try {
      const res = await fetch("/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });

      if (!res.ok) {
        const body = await res.json();
        setError(body.detail as QueryError);
        setStatus("error");
        return;
      }

      const data = await res.json();
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.answer, citations: data.citations },
      ]);
      setStatus("idle");
    } catch {
      setError({
        error: "network_error",
        message: "Could not reach the server. Is the backend running?",
      });
      setStatus("error");
    }
  }

  return (
    <div className="flex flex-1 flex-col items-center bg-background">
      <main className="flex w-full max-w-3xl flex-1 flex-col px-4 py-8">
        <MessageList messages={messages} />

        {status === "error" && error && (
          <p className="pb-2 text-sm text-destructive">
            [{error.error}] {error.message}
          </p>
        )}

        <ChatInput onSubmit={handleSubmit} disabled={status === "loading"} />
      </main>
    </div>
  );
}
