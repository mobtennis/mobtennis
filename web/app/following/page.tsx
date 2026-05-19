import { GetTheAppCard } from "@/components/GetTheAppCard";

export const metadata = {
  title: "Following",
  // Personalised, device-local state — nothing for a crawler to anchor on.
  robots: { index: false, follow: true },
};

export default function FollowingPage() {
  return (
    <div className="space-y-4 pt-2">
      <header className="text-center">
        <h1 className="text-2xl font-bold tracking-tight">Following lives in the app</h1>
        <p className="mt-2 text-sm text-text-secondary">
          Mobtennis is faster and more personal on your phone. No account needed.
        </p>
      </header>
      <GetTheAppCard action="follow your favourites" />
      <FeatureList />
    </div>
  );
}

function FeatureList() {
  const items = [
    { title: "Follow players & tournaments", body: "Tap the star anywhere in the app. Your follows live on your device." },
    { title: "Score alerts", body: "Get pinged when your players are about to take the court — and when they win." },
    { title: "No sign-up", body: "Open the app and you're in. Authenticate later only if you switch devices." },
  ];
  return (
    <ul className="space-y-2">
      {items.map((it) => (
        <li key={it.title} className="rounded-md border border-ink-700 bg-ink-900 p-3">
          <h3 className="text-sm font-semibold">{it.title}</h3>
          <p className="mt-1 text-xs text-text-secondary">{it.body}</p>
        </li>
      ))}
    </ul>
  );
}
