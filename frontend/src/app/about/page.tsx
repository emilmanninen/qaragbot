export default function AboutPage() {
  return (
    <div className="flex flex-1 flex-col items-center bg-background p-4 sm:p-8">
      <main className="flex w-full max-w-3xl flex-1 flex-col rounded-2xl border border-border bg-card p-6 shadow-lg sm:p-8">
        <h1 className="text-xl font-semibold text-foreground">
          About this project
        </h1>
        <p className="mt-4 text-sm text-muted-foreground">
          A small RAG (Retrieval-Augmented Generation) chatbot practice
          project. It answers questions about Kela&apos;s Finnish
          higher-education benefits, such as study grants, student loans,
          and related support. Every answer cites the specific source
          document it came from. Currently only available in Finnish.
        </p>
        <p className="mt-4 text-sm text-muted-foreground">
          For more information:{" "}
          <a
            href="https://github.com/emilmanninen/qaragbot"
            target="_blank"
            rel="noopener noreferrer"
            className="text-foreground underline underline-offset-4 hover:text-primary"
          >
            https://github.com/emilmanninen/qaragbot
          </a>
        </p>
        <div className="mt-6 rounded-lg border border-border bg-muted p-3 text-sm text-muted-foreground">
          <span className="font-medium text-foreground">Disclaimer:</span>{" "}
          this is an independent portfolio project, not an official Kela
          product or financial/benefits advice. Always verify current
          information directly at{" "}
          <a
            href="https://www.kela.fi"
            target="_blank"
            rel="noopener noreferrer"
            className="text-foreground underline underline-offset-4 hover:text-primary"
          >
            kela.fi
          </a>
          . It is deliberately not production-ready for a domain where a
          wrong answer has financial consequences — see the GitHub repo for
          the scope decisions behind that.
        </div>
        <div className="mt-4 rounded-lg border border-border bg-muted p-3 text-sm text-muted-foreground">
          <span className="font-medium text-foreground">Note:</span>{" "}
          if the chatbot doesn&apos;t respond/errors, it&apos;s likely because this
          demo runs on the free Gemini API tier, capped at 20 requests/day,
          rather than a paid one.
        </div>
      </main>
    </div>
  );
}
