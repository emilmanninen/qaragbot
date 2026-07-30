"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

type ChatInputProps = {
  onSubmit: (question: string) => void;
  disabled?: boolean;
};

export function ChatInput({ onSubmit, disabled }: ChatInputProps) {
  const [value, setValue] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const question = value.trim();
    if (!question || disabled) return;
    onSubmit(question);
    setValue("");
  }

  return (
    <form onSubmit={handleSubmit} className="flex w-full gap-2">
      <Textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Ask a question..."
        disabled={disabled}
        className="min-h-12 flex-1 resize-none"
      />
      <Button type="submit" disabled={disabled || !value.trim()}>
        Send
      </Button>
    </form>
  );
}
