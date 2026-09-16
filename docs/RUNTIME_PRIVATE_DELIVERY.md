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

## Provenance layers

`core`, `market`, `dna`, and `neuron` are provenance labels, not independent
model authorities. Each successful snapshot contains the current JSON tree from
the OIDC-attested `main` ref. The reader resolves duplicate logical paths from
the most recently activated head. The `core` publication also rebuilds the lazy
`data/delivery/*` Pages bundles before snapshotting them.

This does **not** alter model probability, thresholds, weights, training,
Player DNA, Surface Elo, Symphony 2, rebuilt Neuron, PLAYABLE, settlement, or
iNeed$ calculations.

## Cutover gate

Do not remove the existing generated-data commits or exclude B/C files from
Pages until all of the following are true:

1. The staging workflow has successfully populated heads for live producer runs.
2. Authenticated-user reads of tier B pass against real Supabase Auth.
3. Admin reads of tier C pass and non-admin reads are rejected.
4. Returned object hashes match the source snapshot hashes.
5. Current Superbet/PLAYABLE freshness is unchanged under concurrent refreshes.
6. Frontend private-read fallback/telemetry is proven before public B/C removal.
7. Only then remove generated-data pushes, stop publishing B/C through Pages,
   and enable required-PR/required-check protection on `main`.

Until that gate, staging failures must not be treated as proof that the
production model/data pipeline is wrong; the old delivery path is still
authoritative.
