export const metadata = {
  title: "Contact",
  description: "How to reach the people behind Mob Tennis.",
};

export default function ContactPage() {
  return (
    <article className="space-y-6 pt-2">
      <header>
        <h1 className="text-2xl font-bold tracking-tight">Contact</h1>
        <p className="mt-1 text-sm text-text-secondary">
          A small project, but a real one. Here&apos;s how to reach us.
        </p>
      </header>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Bugs and feature requests</h2>
        <p className="text-sm text-text-secondary">
          The fastest route. Open an issue at{" "}
          <a
            href="https://github.com/mobtennis/mobtennis/issues"
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent underline decoration-dotted underline-offset-4 hover:text-accent-dim"
          >
            github.com/mobtennis/mobtennis/issues
          </a>
          . A URL plus a one-line description is plenty — every issue gets read.
          You don&apos;t need a GitHub account to read the tracker, but you
          will to file an issue. If GitHub isn&apos;t an option, write to{" "}
          <a
            href="mailto:tsi@tsi.is"
            className="text-accent underline decoration-dotted underline-offset-4 hover:text-accent-dim"
          >
            tsi@tsi.is
          </a>{" "}
          and TSÍ will forward it on.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Corrections</h2>
        <p className="text-sm text-text-secondary">
          Spot a wrong score, a misidentified player, a bracket that
          doesn&apos;t match the draw sheet? Open an issue with the URL of the
          page and what should be there. See{" "}
          <a
            href="/standards#accuracy"
            className="text-accent underline decoration-dotted underline-offset-4 hover:text-accent-dim"
          >
            Editorial standards
          </a>{" "}
          for the broader picture.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Press and partnerships</h2>
        <p className="text-sm text-text-secondary">
          The Tennis Association of Iceland (TSÍ) handles all press,
          partnership, sponsorship, and commercial inquiries — see{" "}
          <a
            href="/about"
            className="text-accent underline decoration-dotted underline-offset-4 hover:text-accent-dim"
          >
            About
          </a>{" "}
          for the funding arrangement.
        </p>
        <p className="text-sm text-text-secondary">
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

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Privacy requests</h2>
        <p className="text-sm text-text-secondary">
          Mob Tennis stores follow-state on your own device and doesn&apos;t
          maintain user accounts — there&apos;s nothing for us to delete
          server-side. For everything else, see the{" "}
          <a
            href="/privacy"
            className="text-accent underline decoration-dotted underline-offset-4 hover:text-accent-dim"
          >
            Privacy Policy
          </a>
          .
        </p>
      </section>
    </article>
  );
}
