# Mobtennis — Mobile

Expo + Expo Router + TypeScript + NativeWind. Same FastAPI backend as the web.

## Run it

Make sure the backend is running (`make backend` from repo root, port 8000).

```bash
cd mobile
npm install
npm run ios            # iOS Simulator (requires Xcode)
# or
npm run android        # Android emulator
# or
npm start              # interactive — pick a platform
```

The simulator launches Expo Go's dev client and the app hot-reloads on save.

## API base URL

By default the app talks to `http://localhost:8000`. For the **iOS Simulator** that
works as-is. For a **physical iPhone** on the same Wi-Fi, change `app.json`:

```json
"extra": { "apiBaseUrl": "http://<your-mac-lan-ip>:8000" }
```

(get your IP with `ipconfig getifaddr en0`).

## Architecture

```
mobile/
├── app/                Expo Router routes (file-based, like Next.js App Router)
│   ├── _layout.tsx           QueryClient provider, root Stack
│   ├── (tabs)/                Bottom-tab group
│   │   ├── _layout.tsx       Tabs config (Home / Live / Events / Following / Search)
│   │   ├── index.tsx         Home
│   │   ├── live.tsx
│   │   ├── tournaments.tsx
│   │   ├── following.tsx
│   │   └── search.tsx
│   ├── players/[slug].tsx
│   ├── tournaments/[slug]/[year].tsx
│   ├── matches/[id].tsx
│   └── h2h/[matchup].tsx
├── components/         Shared UI (mirrors web/components 1:1 in spirit)
└── lib/
    ├── api.ts          fetch() client + types (mirror of web/lib/api.ts)
    ├── device.ts       Device-bound account: UUID in SecureStore
    ├── follows.ts      Follow API (X-User-Token header)
    ├── format.ts
    └── tier.ts         Tournament tier weights for sort
```

## Identity model

No signup. On first launch we generate a UUID and persist it in iOS Keychain /
Android Keystore via `expo-secure-store`. Every follow request sends it as
`X-User-Token`. Account migration to a different device is a future feature
(it's the only path that needs auth).

## Design

Same Tailwind tokens as the web — light/sunny palette, grass-green accents.
NativeWind translates Tailwind classes to RN styles, so component code is
nearly identical to the web version.

## Push notifications

Not yet wired. Plan: `expo-notifications` + Expo Push Service. Subscribe a
device token to topics like `player-{slug}` and `match-{id}-status`; backend
fans out via Expo's push API on score events.
