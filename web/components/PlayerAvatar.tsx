import { flagEmoji } from "@/lib/format";

type Props = {
  name: string;
  imageUrl?: string | null;
  countryCode?: string | null;
  size?: "sm" | "md";
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
  return (
    <div className={`relative shrink-0 ${sizeCls}`}>
      <div className="flex h-full w-full items-center justify-center overflow-hidden rounded-full bg-ink-700 font-semibold text-text-primary">
        {imageUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={imageUrl} alt={name} className="h-full w-full object-cover" />
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
