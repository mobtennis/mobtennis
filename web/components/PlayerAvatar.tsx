import { commonsImgVariant, flagEmoji } from "@/lib/format";

type Props = {
  name: string;
  imageUrl?: string | null;
  countryCode?: string | null;
  size?: "sm" | "md";
};

// Map render size → Commons thumbnail width (CSS px × 2 for retina,
// rounded to a friendly multiple). Anything below the 96px Commons
// thumb is impossibly small even on a 1× phone screen.
const THUMB_PX: Record<NonNullable<Props["size"]>, number> = {
  sm: 96,  // 32px CSS avatar × 3 (oversampled for crispness)
  md: 96,  // 40px CSS avatar × ~2.4
};

export function PlayerAvatar({ name, imageUrl, countryCode, size = "sm" }: Props) {
  const sizeCls = size === "sm" ? "h-8 w-8 text-xs" : "h-10 w-10 text-sm";
  const initials = name
    .split(" ")
    .map((p) => p[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase();
  // Rewrite Wikimedia full-res URLs to the appropriate thumb. Cuts
  // payload from megabytes to ~5-15KB per avatar. Non-Commons URLs
  // pass through unchanged.
  const thumb = commonsImgVariant(imageUrl, THUMB_PX[size]);
  return (
    <div className={`relative shrink-0 ${sizeCls}`}>
      <div className="flex h-full w-full items-center justify-center overflow-hidden rounded-full bg-ink-700 font-semibold text-text-primary">
        {thumb ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={thumb} alt={name} className="h-full w-full object-cover" />
        ) : (
          <span>{initials}</span>
        )}
      </div>
      {countryCode && (
        <span className="absolute -bottom-1 -right-1 text-[10px]">{flagEmoji(countryCode)}</span>
      )}
    </div>
  );
}
