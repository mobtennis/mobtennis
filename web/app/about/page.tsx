export const metadata = { title: "About Mob Tennis" };

export default function AboutPage() {
  return (
    <article className="space-y-6 pt-2">
      <header>
        <h1 className="text-2xl font-bold tracking-tight">About Mob Tennis</h1>
        <p className="mt-1 text-sm text-text-secondary">
          Live scores, draws, and tennis news. Built in Iceland; profits go to
          junior tennis here.
        </p>
      </header>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">What it is</h2>
        <p className="text-sm text-text-secondary">
          A fast, clean tennis app — live scores, brackets, head-to-heads, news
          and highlights — without the bloat and signup walls of the bigger
          sites. Free to use.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Who runs it</h2>
        <p className="text-sm text-text-secondary">
          Mob Tennis was built by{" "}
          <a
            href="https://claude.com"
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent underline decoration-dotted underline-offset-4 hover:text-accent-dim"
          >
            Claude
          </a>
          , with a single developer from Iceland in the coaching box, mostly
          applauding. There&apos;s no founder-profile angle here on purpose —
          the project is about the sport and the cause.
        </p>
        <p className="text-sm text-text-secondary">
          On the record: profits from Mob Tennis flow to the{" "}
          <strong>Tennis Association of Iceland (TSÍ)</strong>, earmarked for
          junior development. TSÍ administers the funds and handles all press
          and partnership questions.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Where the money goes</h2>
        <p className="text-sm text-text-secondary">
          Mob Tennis runs on free hosting tiers, a small live-data subscription,
          and ad impressions. After hosting costs,{" "}
          <strong>
            100% of revenue is routed to TSÍ&apos;s junior development programs
          </strong>{" "}
          — coaching, court time, and travel grants so Icelandic juniors can
          compete more often against players outside the country.
        </p>
        <p className="text-sm text-text-secondary">
          The arrangement is reviewed annually by TSÍ&apos;s board. Aggregate
          revenue and donation figures are published on this page once per
          year.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Open source</h2>
        <p className="text-sm text-text-secondary">
          The full source is available at{" "}
          <a
            href="https://github.com/mobtennis/mobtennis"
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent underline decoration-dotted underline-offset-4 hover:text-accent-dim"
          >
            github.com/mobtennis/mobtennis
          </a>{" "}
          under the MIT license. The repository carries no personal authorship;
          the project belongs to TSÍ.
        </p>
        <p className="text-sm text-text-secondary">
          You don&apos;t need to be a developer to take part. Got an idea for a
          feature, a stat you wish you could see, a player or tournament page
          that&apos;s missing something? Open an issue on GitHub — a one-line
          description is plenty, and every idea gets read. If you do write
          code, pull requests are equally welcome.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Press &amp; partnerships</h2>
        <p className="text-sm text-text-secondary">
          Press inquiries and partnership proposals go through TSÍ:{" "}
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
          .
        </p>
      </section>
    </article>
  );
}
