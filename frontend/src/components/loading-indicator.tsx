export function LoadingIndicator() {
  return (
    <div className="flex justify-start">
      <div
        role="status"
        className="flex items-center gap-1 rounded-lg bg-muted px-4 py-3"
      >
        <span className="sr-only">Loading answer…</span>
        <span
          aria-hidden="true"
          className="h-2 w-2 animate-bounce rounded-full bg-foreground/40 [animation-delay:-0.3s]"
        />
        <span
          aria-hidden="true"
          className="h-2 w-2 animate-bounce rounded-full bg-foreground/40 [animation-delay:-0.15s]"
        />
        <span
          aria-hidden="true"
          className="h-2 w-2 animate-bounce rounded-full bg-foreground/40"
        />
      </div>
    </div>
  );
}
