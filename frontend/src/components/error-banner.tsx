import type { QueryError } from "@/lib/types";

const ERROR_COPY: Record<string, (err: QueryError) => string> = {
  quota_exhausted: (err) =>
    `The AI service${err.provider ? ` (${err.provider})` : ""} is temporarily out of capacity. Please try again shortly.`,
  llm_provider_error: () =>
    "Something went wrong generating an answer. Please try again.",
  rate_limited: () =>
    "Too many requests in a short time. Please wait a bit and try again.",
  daily_limit_reached: () =>
    "This demo has hit its daily question limit. Please try again tomorrow.",
  network_error: () =>
    "Could not reach the server. Is the backend running?",
};

export function ErrorBanner({ error }: { error: QueryError }) {
  const getMessage = ERROR_COPY[error.error] ?? (() => "An unexpected error occurred.");

  return (
    <p className="pb-2 text-sm text-destructive" role="alert">
      {getMessage(error)}
    </p>
  );
}