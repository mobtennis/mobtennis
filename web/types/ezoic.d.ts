// Ambient types for the Ezoic standalone (sa.min.js) loader.
//
// Only relevant when NEXT_PUBLIC_AD_NETWORK = "ezoic". Safe to delete
// this file when switching off Ezoic — no other code references the
// `Window.ezstandalone` augmentation outside `components/Ezoic*.tsx`
// and the `ezoic` branch in `components/AdSlot.tsx`.

declare global {
  interface Window {
    ezstandalone?: {
      cmd: Array<() => void>;
      showAds: (...ids: number[]) => void;
      destroyPlaceholders: (...ids: number[]) => void;
      refreshAds?: (...ids: number[]) => void;
    };
  }
}

export {};
