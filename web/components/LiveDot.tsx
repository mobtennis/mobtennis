// Two layered animations:
//   • outer ring uses Tailwind's built-in `animate-ping` (scale 1→2,
//     opacity 1→0) for the broadcast / radar look — instantly readable
//     as "live right now"
//   • text gets a subtle `animate-pulse` so it breathes without being
//     flashy. Goes well together; either alone reads as decorative.
export function LiveDot({ label = true }: { label?: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="relative inline-flex h-2 w-2">
        <span className="absolute inset-0 inline-flex rounded-full bg-live opacity-75 animate-ping" />
        <span className="relative inline-flex h-2 w-2 rounded-full bg-live" />
      </span>
      {label && (
        <span className="animate-pulse text-[10px] font-bold uppercase tracking-wider text-live">
          Live
        </span>
      )}
    </span>
  );
}

/** Static amber dot for matches that were live but are currently
 * paused (rain delay etc.). Same affordance as LiveDot — "this is an
 * ongoing match you can keep tracking" — but no animation so it reads
 * as "paused" rather than "broadcasting right now." */
export function SuspendedDot({ label = true }: { label?: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="inline-flex h-2 w-2 rounded-full bg-amber-400" />
      {label && (
        <span className="text-[10px] font-bold uppercase tracking-wider text-amber-400">
          Suspended
        </span>
      )}
    </span>
  );
}
