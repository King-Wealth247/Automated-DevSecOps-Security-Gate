# Fly.io — TEMPORARY interim deployment (while AWS OIDC is blocked)

**This is not the project's real deployment target.** AWS EC2, reached via
the OIDC-federated role in `infra/aws/`, remains that (FR-25/FR-26). This
folder exists only because task 4.3's AWS OIDC federation is currently
blocked on an AWS-side new-account hold (see `IMPLEMENTATION_PLAN.md`, §20)
— it's a stand-in so the pipeline's PASS→deploy half can still be
demonstrated while that clears. See `IMPLEMENTATION_PLAN.md`'s "Temporary
Deployment Strategy" section for the full evaluation and rationale,
including why Vercel specifically was rejected first.

## Why Fly.io and not something else

Juice Shop needs a real, persistent process — it writes to a local SQLite
file (`data/juiceshop.sqlite`), writes uploaded files to disk
(`uploads/complaints/`), and depends on long-lived Socket.IO connections for
core challenge tracking. Fly.io runs actual persistent Firecracker VMs
("Machines"), not per-request serverless functions, so all of that works
unmodified — unlike Vercel, which was evaluated and rejected for exactly
these reasons.

**Chain of custody, preserved:** this setup deploys the *exact* Docker image
`publish` already built, Trivy-scanned, and pushed to GHCR
(`flyctl deploy --image ghcr.io/.../juice-shop:<sha>`) — Fly never rebuilds
`juice-shop/Dockerfile` itself. That's the same "deploy exactly what was
scanned" guarantee the AWS EC2 path provides, and the main reason this is a
faithful stand-in rather than just "a different way to get it online."

**Known limitation, deliberately accepted:** no Fly Volume is configured, so
local disk (the SQLite DB, uploads) persists for the life of the *running*
machine but resets on a redeploy/restart. This is fine for a temporary demo
(`min_machines_running: 1` and `auto_stop_machines: false` in `fly.toml`
keep one machine running continuously, so it won't reset on its own). Adding
a persistent Fly Volume later is possible, but the container runs as a
non-root user (UID 65532, a distroless image with no shell) — getting a
mounted volume's permissions right needs real testing against a live app,
so it's deliberately deferred rather than guessed at here.

## Prerequisites

- A Fly.io account (free tier / trial credit is enough for this single
  small, always-on shared-cpu-1x/512MB machine).
- `flyctl` installed locally, to do the one-time app setup.

## Step 0 — Install flyctl and log in

```powershell
# Windows (PowerShell)
iwr https://fly.io/install.ps1 -useb | iex
# close and reopen the shell, then:
flyctl auth login
```

## Step 1 — Make the GHCR image pullable by Fly

The `publish` job already pushes to `ghcr.io/king-wealth247/juice-shop`.
GitHub Container Registry packages are **private by default**, even in a
public repo, so Fly needs either:

- **Simpler — make the package public** (matches this project's already-public
  posture): GitHub → your profile → **Packages** → `juice-shop` → **Package
  settings** → **Change visibility** → **Public**. No further Fly-side
  registry auth needed.
- **Or keep it private**: create a GitHub PAT with `read:packages` scope,
  then `fly secrets set REGISTRY_AUTH_TOKEN=<pat>` and reference it — more
  setup, only do this if you specifically don't want the image public.

## Step 2 — Create the Fly app (one-time)

From the repository root:

```powershell
flyctl apps create devsecops-juice-shop-temp
```

If that name is taken (Fly app names are globally unique), pick another and
update the `app = "..."` line in `juice-shop/fly.toml` to match.

## Step 3 — Get a deploy token and add it to GitHub

```powershell
flyctl tokens create deploy -x 999999h
```

Copy the printed token. Repo → **Settings → Secrets and variables → Actions
→ Secrets** → **New repository secret** → name it `FLY_API_TOKEN` → paste
the token. This is a real credential — never paste it in chat.

## Step 4 — First deploy (manual, to prove it works before wiring CI)

```powershell
$env:IMAGE = "ghcr.io/king-wealth247/juice-shop:<a-real-published-sha>"
flyctl deploy --config juice-shop/fly.toml --image $env:IMAGE
```

Use a `<sha>` you already know `publish` pushed (check the repo's Packages
tab, or a prior `publish`-job log) — this proves the Fly side works before
relying on the automated `deploy-flyio-temp` CI job.

## Step 5 — Let CI do it automatically from here

Once `FLY_API_TOKEN` is set, the `deploy-flyio-temp` job in `ci.yml` runs
automatically after every genuine `PASS` (same gate as `publish` — a BLOCK
skips it, exactly like GHCR publishing). Trigger it the same way you did
`publish`'s live validation: a `workflow_dispatch` run with
`use_clean_fixtures: true`, or a real clean push once one exists.

## Verify

```powershell
flyctl status --app devsecops-juice-shop-temp
```

or open `https://devsecops-juice-shop-temp.fly.dev` directly (substitute
your actual app name if you changed it).

## Troubleshooting

- `flyctl deploy` fails to pull the image → the GHCR package is still
  private and Fly has no registry credential — see Step 1.
- App creates but the machine keeps crashing/restarting → check
  `flyctl logs --app devsecops-juice-shop-temp`; distroless images produce
  no shell-level diagnostics, so the app's own stdout/stderr is all you get.
- Deploy succeeds but the site 502s → `internal_port` in `fly.toml` must
  stay `3000`, matching the Dockerfile's `EXPOSE 3000` — don't change one
  without the other.
- Wrong image pulled / stale demo → confirm `IMAGE_TAG` in the CI job
  actually matches a `sha` that `publish` pushed in the *same* run, not a
  leftover local `$env:IMAGE` from a manual test.

## Decommissioning once AWS OIDC is unblocked

This is explicitly temporary. Once task 4.3 clears and the real AWS EC2
deploy path (task 4.5) is live, retire this: `flyctl apps destroy
devsecops-juice-shop-temp`, remove the `deploy-flyio-temp` job from
`ci.yml`, remove `juice-shop/fly.toml`, remove this folder, and delete the
`FLY_API_TOKEN` secret. Do this deliberately, not by accident — until then,
both paths can coexist (see `IMPLEMENTATION_PLAN.md`).
