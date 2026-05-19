export const metadata = { title: "Privacy Policy" };

export default function PrivacyPage() {
  return (
    <article className="space-y-6 pt-2">
      <header>
        <h1 className="text-2xl font-bold tracking-tight">Privacy Policy</h1>
        <p className="mt-1 text-sm text-text-secondary">
          Last updated: 18 May 2026
        </p>
      </header>

      <section className="space-y-2 text-sm text-text-secondary">
        <p>
          Mobtennis (&quot;we&quot;, &quot;us&quot;) operates{" "}
          <a
            href="https://mob.tennis"
            className="text-accent underline decoration-dotted underline-offset-4 hover:text-accent-dim"
          >
            mob.tennis
          </a>{" "}
          and its mobile applications. This page explains what data we collect,
          why, and how to opt out of optional tracking.
        </p>
        <p>
          We try to minimise data collection. Where it would have made the
          product noticeably worse for users to drop something entirely, we
          collect it; otherwise we don&apos;t.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Information we collect</h2>
        <p className="text-sm text-text-secondary">
          When you visit Mobtennis, our servers automatically log a small set
          of technical details with each request:
        </p>
        <ul className="ml-4 list-disc space-y-1 text-sm text-text-secondary">
          <li>IP address (truncated before storage)</li>
          <li>User agent (browser and device type)</li>
          <li>The URL you requested and the URL that referred you</li>
          <li>Timestamp of the request</li>
        </ul>
        <p className="text-sm text-text-secondary">
          These logs are kept for up to 30 days and are used to debug errors,
          detect abuse, and produce aggregate traffic statistics. We do not
          associate request logs with any identifier you provide elsewhere on
          the site.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Cookies and local storage</h2>
        <p className="text-sm text-text-secondary">
          Mobtennis uses{" "}
          <code className="rounded bg-ink-900 px-1 py-0.5 text-[11px]">
            localStorage
          </code>{" "}
          (in your browser) to remember a small device-bound identifier — this
          is what powers features like &quot;Following&quot; without requiring
          you to create an account. The identifier is stored on your device,
          never transmitted in plain text, and cleared when you clear your
          browser&apos;s storage.
        </p>
        <p className="text-sm text-text-secondary">
          We do not set first-party cookies for marketing or cross-site
          tracking.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Analytics</h2>
        <p className="text-sm text-text-secondary">
          We use PostHog for product analytics — page views, button clicks,
          and feature usage. Analytics events are tied to the same
          device-bound identifier described above, not to any personal
          information. We use this data to understand which features are used
          and to find bugs.
        </p>
        <p className="text-sm text-text-secondary">
          To opt out of analytics, enable &quot;Do Not Track&quot; in your
          browser; we honour that signal and skip analytics on every page
          load.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Advertising</h2>
        <p className="text-sm text-text-secondary">
          Mobtennis displays ads to fund the project (profits flow to the
          Tennis Association of Iceland — see{" "}
          <a
            href="/about"
            className="text-accent underline decoration-dotted underline-offset-4 hover:text-accent-dim"
          >
            About
          </a>
          ). Ads are served by third-party networks (currently Ezoic; previously
          and possibly again in the future Google AdSense). These networks
          place their own cookies and may collect a subset of the data
          described above plus information about ads you interact with.
        </p>
        <p className="text-sm text-text-secondary">
          Our ad partners participate in the IAB Transparency &amp; Consent
          Framework. If you&apos;re in a region that requires explicit
          consent (EEA, UK, Switzerland, California), you&apos;ll see a
          consent banner the first time you visit; you can change your
          preferences at any time by clearing your browser&apos;s cookies for
          this site.
        </p>
        <p className="text-sm text-text-secondary">
          For more detail on what our ad partners collect:{" "}
          <a
            href="https://policies.google.com/technologies/partner-sites"
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent underline decoration-dotted underline-offset-4 hover:text-accent-dim"
          >
            Google
          </a>
          {" · "}
          <a
            href="https://www.ezoic.com/privacy-policy/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent underline decoration-dotted underline-offset-4 hover:text-accent-dim"
          >
            Ezoic
          </a>
          .
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Third-party content</h2>
        <p className="text-sm text-text-secondary">
          We embed YouTube highlight videos via their iframe player. When you
          play a video, YouTube applies its own privacy policy. We use the
          <code className="rounded bg-ink-900 px-1 py-0.5 text-[11px]">
            {" "}youtube-nocookie.com{" "}
          </code>
          domain so YouTube cookies aren&apos;t set until you actually start
          playing.
        </p>
        <p className="text-sm text-text-secondary">
          Player photos and live data come from{" "}
          <a
            href="https://api-tennis.com"
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent underline decoration-dotted underline-offset-4 hover:text-accent-dim"
          >
            api-tennis.com
          </a>{" "}
          and Jeff Sackmann&apos;s public datasets. Bracket structure comes
          from Wikipedia. None of these involve sending your information
          anywhere.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Your rights</h2>
        <p className="text-sm text-text-secondary">
          Because we don&apos;t associate request logs or analytics events
          with personal information, there&apos;s typically nothing to delete
          on your request. To delete your local follow-list and device
          identifier, clear your browser storage for{" "}
          <code className="rounded bg-ink-900 px-1 py-0.5 text-[11px]">
            mob.tennis
          </code>
          .
        </p>
        <p className="text-sm text-text-secondary">
          For any GDPR, CCPA, or other data-rights enquiry, contact the Tennis
          Association of Iceland at{" "}
          <a
            href="mailto:tsi@tsi.is"
            className="text-accent underline decoration-dotted underline-offset-4 hover:text-accent-dim"
          >
            tsi@tsi.is
          </a>
          .
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Changes to this policy</h2>
        <p className="text-sm text-text-secondary">
          We&apos;ll update the &quot;Last updated&quot; date at the top of
          this page when this policy changes. Material changes (new data
          collection, new sharing) will be summarised in a banner on the
          home page for at least 14 days.
        </p>
      </section>
    </article>
  );
}
