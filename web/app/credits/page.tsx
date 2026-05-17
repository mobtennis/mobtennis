export const metadata = { title: "Credits & data sources" };

export default function CreditsPage() {
  return (
    <article className="space-y-6 pt-2">
      <header>
        <h1 className="text-2xl font-bold tracking-tight">Credits & data sources</h1>
        <p className="mt-1 text-sm text-text-secondary">
          Mobtennis stands on the shoulders of a few generous data sets.
        </p>
      </header>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Historical player & match data</h2>
        <p className="text-sm text-text-secondary">
          Player biographies, historical match records, and tournament metadata
          are derived from{" "}
          <a
            href="https://github.com/JeffSackmann/tennis_atp"
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent underline decoration-dotted underline-offset-4 hover:text-accent-dim"
          >
            Jeff Sackmann's <code>tennis_atp</code>
          </a>{" "}
          and{" "}
          <a
            href="https://github.com/JeffSackmann/tennis_wta"
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent underline decoration-dotted underline-offset-4 hover:text-accent-dim"
          >
            <code>tennis_wta</code>
          </a>{" "}
          datasets, distributed under the{" "}
          <a
            href="https://creativecommons.org/licenses/by-nc-sa/4.0/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent underline decoration-dotted underline-offset-4 hover:text-accent-dim"
          >
            Creative Commons Attribution-NonCommercial-ShareAlike 4.0
          </a>{" "}
          license. We're enormously grateful for that work — it's the closest thing
          tennis has to a community-maintained record.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Live scores & fixtures</h2>
        <p className="text-sm text-text-secondary">
          Live match data is licensed from{" "}
          <a
            href="https://api-tennis.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent underline decoration-dotted underline-offset-4 hover:text-accent-dim"
          >
            api-tennis.com
          </a>
          .
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Bracket structure & seeds</h2>
        <p className="text-sm text-text-secondary">
          Draw structure and seed information for top-tier events (Grand Slams,
          ATP/WTA 1000) is sourced from the corresponding{" "}
          <a
            href="https://en.wikipedia.org/wiki/Tennis"
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent underline decoration-dotted underline-offset-4 hover:text-accent-dim"
          >
            English Wikipedia
          </a>{" "}
          tournament-draw pages, made available under the{" "}
          <a
            href="https://creativecommons.org/licenses/by-sa/4.0/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent underline decoration-dotted underline-offset-4 hover:text-accent-dim"
          >
            Creative Commons Attribution-ShareAlike 4.0
          </a>{" "}
          license.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">News</h2>
        <p className="text-sm text-text-secondary">
          News headlines and links are aggregated from the public RSS feeds of
          the respective publications. Each item links back to the original
          source. We don't host article text — only titles, summaries, and
          attribution.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Player photos & flags</h2>
        <p className="text-sm text-text-secondary">
          Player photographs are provided by api-tennis. Country flags are the
          standard Unicode regional-indicator emoji rendered by your device.
        </p>
      </section>
    </article>
  );
}
