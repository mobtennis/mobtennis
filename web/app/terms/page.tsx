export const metadata = { title: "Terms of Use" };

export default function TermsPage() {
  return (
    <article className="space-y-6 pt-2">
      <header>
        <h1 className="text-2xl font-bold tracking-tight">Terms of Use</h1>
        <p className="mt-1 text-sm text-text-secondary">
          Last updated: 18 May 2026
        </p>
      </header>

      <section className="space-y-2 text-sm text-text-secondary">
        <p>
          These terms apply to{" "}
          <a
            href="https://mob.tennis"
            className="text-accent underline decoration-dotted underline-offset-4 hover:text-accent-dim"
          >
            mob.tennis
          </a>{" "}
          and any current or future Mob Tennis mobile apps (the
          &quot;Service&quot;). By using the Service you agree to these
          terms. If you don&apos;t, please don&apos;t use it.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">What Mob Tennis is</h2>
        <p className="text-sm text-text-secondary">
          Mob Tennis is an independent, fan-built tennis information site.
          We aggregate live scores, draws, news, and highlights from public
          sources, and present them in a fast, clean format. We are not
          affiliated with the ATP, WTA, ITF, or any individual tournament.
          Profits flow to the Tennis Association of Iceland — see{" "}
          <a
            href="/about"
            className="text-accent underline decoration-dotted underline-offset-4 hover:text-accent-dim"
          >
            About
          </a>
          .
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Accuracy</h2>
        <p className="text-sm text-text-secondary">
          We do our best to keep data accurate and timely, but Mob Tennis is
          an aggregator: live scores can lag, brackets can briefly
          mis-display while upstream sources update, and historical data is
          only as good as our underlying datasets. The Service is provided
          &quot;as is&quot; — don&apos;t use it for betting decisions, and
          don&apos;t rely on it where accuracy genuinely matters.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Acceptable use</h2>
        <p className="text-sm text-text-secondary">You agree not to:</p>
        <ul className="ml-4 list-disc space-y-1 text-sm text-text-secondary">
          <li>Scrape the Service at a rate that strains its hosting (please use the linked upstream sources directly if you need bulk data — they&apos;re in the credits)</li>
          <li>Use the Service to harass any player or person</li>
          <li>Resell or rebrand the Service&apos;s output as your own</li>
          <li>Bypass paywalls, rate limits, or content protections</li>
        </ul>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Content attribution</h2>
        <p className="text-sm text-text-secondary">
          Historical data is sourced from Jeff Sackmann&apos;s public
          datasets under CC BY-NC-SA 4.0 — full attribution on the{" "}
          <a
            href="/credits"
            className="text-accent underline decoration-dotted underline-offset-4 hover:text-accent-dim"
          >
            Credits
          </a>{" "}
          page. Bracket structure comes from Wikipedia under CC BY-SA. News
          headlines link to their original publishers; we don&apos;t host
          article text. Highlight videos play via YouTube&apos;s standard
          iframe embed — playback, monetisation, and analytics stay with
          the channel.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Open source</h2>
        <p className="text-sm text-text-secondary">
          The Service&apos;s source code is available at{" "}
          <a
            href="https://github.com/mobtennis/mobtennis"
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent underline decoration-dotted underline-offset-4 hover:text-accent-dim"
          >
            github.com/mobtennis/mobtennis
          </a>{" "}
          under the MIT license. You&apos;re welcome to fork, contribute, or
          run your own instance.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Advertising</h2>
        <p className="text-sm text-text-secondary">
          We display ads to fund the project. Ads are served by third-party
          networks; see the{" "}
          <a
            href="/privacy"
            className="text-accent underline decoration-dotted underline-offset-4 hover:text-accent-dim"
          >
            Privacy Policy
          </a>{" "}
          for details on what those networks may collect. We try to avoid
          ads that interfere with reading the live score above them; if you
          spot one that does, please report it via the linked GitHub issues.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Liability</h2>
        <p className="text-sm text-text-secondary">
          To the extent permitted by law, neither Mob Tennis nor the Tennis
          Association of Iceland is liable for any loss arising from your
          use of the Service. The Service is provided without warranty of
          any kind.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Changes</h2>
        <p className="text-sm text-text-secondary">
          We&apos;ll update the &quot;Last updated&quot; date when these
          terms change. Continued use of the Service after changes means you
          accept the new terms.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Contact</h2>
        <p className="text-sm text-text-secondary">
          Tennis Association of Iceland —{" "}
          <a
            href="https://tsi.is"
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent underline decoration-dotted underline-offset-4 hover:text-accent-dim"
          >
            tsi.is
          </a>
          {" · "}
          <a
            href="mailto:tsi@tsi.is"
            className="text-accent underline decoration-dotted underline-offset-4 hover:text-accent-dim"
          >
            tsi@tsi.is
          </a>
        </p>
      </section>
    </article>
  );
}
