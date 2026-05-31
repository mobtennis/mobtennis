import { notFound } from "next/navigation";

import { api, type PlayerDetail, type PlayerImage } from "@/lib/api";
import { ImageRow } from "./image-row";

// Disable ISR — this page is admin-only and any data is volatile.
export const revalidate = 0;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  return { title: `Admin · ${slug} photos`, robots: { index: false, follow: false } };
}

export default async function PlayerImagesAdmin({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ key?: string }>;
}) {
  const { slug } = await params;
  const { key } = await searchParams;
  if (!key) {
    return (
      <div className="space-y-3 p-4 text-sm">
        <h1 className="text-lg font-semibold">Admin key required</h1>
        <p className="text-text-secondary">
          Add <code>?key=…</code> to the URL with the configured ADMIN_KEY.
        </p>
      </div>
    );
  }

  // Server-side: fetch the player + all images including hidden ones
  // so the admin can unhide rejected entries. Both calls hit the
  // existing public + admin endpoints.
  const [player, images] = await Promise.all([
    api<PlayerDetail>(`/api/players/${slug}`).catch(() => null),
    api<PlayerImage[]>(`/api/players/${slug}/images?include_hidden=true`).catch(
      () => [] as PlayerImage[],
    ),
  ]);
  if (!player) notFound();

  return (
    <div className="space-y-4 p-3">
      <header className="space-y-1">
        <h1 className="text-xl font-bold tracking-tight">
          Photos for {player.full_name}
        </h1>
        <p className="text-xs text-text-muted">
          {images.length} image{images.length === 1 ? "" : "s"} ·{" "}
          {images.filter((i) => i.is_hidden).length} hidden
        </p>
      </header>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
        {images.map((img) => (
          <ImageRow key={img.id} image={img} slug={slug} adminKey={key} />
        ))}
      </div>

      {images.length === 0 && (
        <p className="text-sm text-text-muted">
          No images yet. Run the enricher CLI:{" "}
          <code className="rounded bg-ink-900 px-1.5 py-0.5">
            python -m scripts.enrich_player_images --slug {slug}
          </code>
        </p>
      )}
    </div>
  );
}
