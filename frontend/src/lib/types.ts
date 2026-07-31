export type Citation = { source_url: string; snippet: string };

export type Message = {
  role: "user" | "assistant";
  content: string;
  citations?: Record<string, Citation>;
};

export type QueryError = { error: string; message: string; provider?: string };
