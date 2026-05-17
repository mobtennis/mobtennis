# Mobtennis

The Fotmob of tennis — fan-first, fast, clean. Live at [mob.tennis](https://mob.tennis).

ATP/WTA live scores, player profiles, tournament draws, head-to-head, news. Two surfaces:

- **Web** — anonymous discovery surface. Live scores, players, tournaments, news, rankings, H2H. Clean shareable URLs. SEO-friendly. No accounts.
- **Apps (in development)** — same data + personalization (follow players, alerts). Account is device-bound by default; authentication only enters the picture for transferring an account between devices.

The web's job is to be fast and fan-friendly for browsing; the app is where loyalty lives.

Profits from Mobtennis flow to the Tennis Association of Iceland (TSÍ),
earmarked for junior development. See [the about page](https://mob.tennis/about)
for the full story.

## Stack

- **Backend** — Python 3.12 + FastAPI + SQLModel + SQLite + APScheduler
- **Frontend** — Next.js 15 (App Router) + TypeScript + Tailwind
- **Mobile** — Expo (React Native) + Expo Router
- **Live data** — pluggable provider (default: api-tennis.com); Jeff Sackmann CSVs for historical/H2H; RSS for news

## Quick start

```bash
cp .env.example .env
make install
make seed       # one-time: ingest Sackmann historical data (~5 min)

# in two terminals:
make backend    # http://localhost:8000  (docs: /docs)
make web        # http://localhost:3000
```

You can run the backend without an `API_TENNIS_KEY` — live polling will be skipped, but rankings, players, tournaments, H2H, and news all work from Sackmann + RSS.

## Architecture

```
mobtennis/
├── backend/                FastAPI + SQLite
│   ├── app/
│   │   ├── api/            HTTP routers
│   │   ├── models/         SQLModel tables
│   │   ├── schemas/        Pydantic response schemas
│   │   ├── services/       providers (live, sackmann, rss, youtube)
│   │   ├── jobs/           APScheduler jobs
│   │   └── db/             session, migrations
│   └── scripts/            one-shot scripts (sackmann_ingest, …)
├── web/                    Next.js 15
│   ├── app/                routes
│   ├── components/         design system
│   └── lib/                api client, follows
├── mobile/                 Expo (React Native)
└── data/                   SQLite db, raw CSVs (gitignored)
```

### Live data — pluggable provider

`app/services/live/` defines `LiveScoresProvider`. Swapping providers
(api-tennis → Sportradar later) is a one-file change.

### URL structure

```
/                          home — live + headlines
/following                 promo page → install the app
/news                      aggregated headlines
/search                    search players / tournaments
/players/[slug]            e.g. /players/carlos-alcaraz
/tournaments/[tour]/[slug] e.g. /tournaments/atp/wimbledon
/matches/[id]              live or completed match detail
/rankings/[tour]           /rankings/atp or /rankings/wta
/h2h/[p1]-vs-[p2]          /h2h/alcaraz-vs-sinner
```

## Contributing

Not a developer? Ideas, bug reports, "I wish this page showed X" notes
are equally welcome — just open an issue. A one-line description is
plenty. If you do write code, pull requests are equally welcome.

The project is intentionally maintained by a single developer (with a
few AI agents in the coaching box), so review can be slow during busy
weeks — but every issue gets read.

## License

MIT — see [LICENSE](LICENSE).
