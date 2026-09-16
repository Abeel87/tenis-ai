# Runtime private delivery staging

Status: **dual-write staging only**. GitHub Pages remains the production data
delivery path until the private path has passed live Auth/read/hash checks.

## Security boundary

- Bucket: `tenis-ai-runtime-private`, private.
- Browser roles have no direct table/storage grants.
- GitHub publishes through `runtime-data-publish` using short-lived GitHub OIDC.
- The publisher pins repository name, immutable repository/owner ids, `main`, and
  `.github/workflows/runtime-private-delivery.yml`.
- Runtime objects are content-addressed (`objects/<sha256>.json`) and immutable.
- A generation becomes active only after the DB confirms every referenced object
  exists and a compare-and-swap head update succeeds.
- `runtime-data-read` revalidates the Supabase user with Auth, rejects banned
  profiles, and only allows tier C to `admin`.
- Unknown JSON defaults to tier C. Tier B is an explicit allowlist.
- The publisher keeps every upload below 45 MiB. This leaves headroom below the
  current 50 MB global Storage upload cap of the Free project; a larger bucket
  object limit does not override the project-level cap.

## Provenance layers

`core`, `market`, `dna`, and `neuron` are provenance labels, not independent
model authorities. Each successful publication contains only the JSON owned by
that producer scope from the OIDC-attested `main` ref:

- `neuron`: only `neuron_current.json`, `neuron_metrics.json`, and
  `neuron_model.json` from the rebuilt Neuron.
- `dna`: `player_dna_*.json` runtime/report artifacts.
- `market`: current results/meta plus Superbet, Symphony 2, market-lab, shadow,
  Surface Elo integration, and related market runtime artifacts.
- `core`: all remaining runtime JSON plus the generated lazy
  `data/delivery/*` projection.

The scopes are mutually exclusive in the publisher. A Neuron refresh therefore
cannot republish large history/market/DNA files, and a market refresh cannot
replace the Neuron or DNA heads.

The `core` publication rebuilds the lazy `data/delivery/*` Pages bundles before
snapshotting them.

### Large history projection

`frontend/data/history.json` is currently larger than the Free project upload
cap. The staging publisher does **not** modify that source file. For the private
`core` generation it creates an ephemeral projection:

- `data/private/history/manifest.json`
- `data/private/history/chunks/0000.json`, `0001.json`, ...

Chunks target 20 MiB and must remain below the publisher's 45 MiB safety cap.
The manifest records the original `data/history.json` SHA-256, source byte size,
entry count, and every chunk's SHA-256/size/entry count. The manifest and chunks
are tier B.

GitHub Pages and the current history UI continue to use the original
`data/history.json` during staging. Public history must not be removed until a
private manifest/chunk reader and fallback have passed Auth E2E and hash checks.

This does **not** alter model probability, thresholds, weights, training,
Player DNA, Surface Elo, Symphony 2, rebuilt Neuron, PLAYABLE, settlement, or
iNeed$ calculations.

## Cutover gate

Do not remove the existing generated-data commits or exclude B/C files from
Pages until all of the following are true:

1. The staging workflow has successfully populated heads for live producer runs.
2. Authenticated-user reads of tier B pass against real Supabase Auth.
3. Admin reads of tier C pass and non-admin reads are rejected.
4. Returned object hashes match the staged manifest/object hashes and the
   history manifest records the canonical source SHA.
5. Current Superbet/PLAYABLE freshness is unchanged under concurrent refreshes.
6. Frontend private-read fallback/telemetry, including history chunk loading, is
   proven before public B/C removal.
7. Only then remove generated-data pushes, stop publishing B/C through Pages,
   and enable required-PR/required-check protection on `main`.

Until that gate, staging failures must not be treated as proof that the
production model/data pipeline is wrong; the old delivery path is still
authoritative.
