# Krexion Deploy — Self-Hosted VPS Runner

**Last updated:** 2026-01-09
**Runner name:** `krexion-vps`  · label: `krexion-vps`
**Location:** `/opt/krexion-runner/` on the customer VPS
**Systemd unit:** `krexion-runner.service` (alias) OR `actions.runner.krexion-com-final-krexion.com-final.krexion-vps.service`

---

## Why this exists

The `krexion-com-final` GitHub org's monthly Actions minutes are a
finite resource — private-repo Linux minutes on the free tier reset
each billing cycle and can be exhausted mid-month. When that happens,
GitHub-hosted `ubuntu-latest` runners never spawn and every workflow
dies at scheduling with `runner_id=0`.

To make **every deploy always succeed regardless of the org's Actions
quota**, we run our own dedicated GitHub Actions runner **on the VPS
itself**. Consumes ZERO GitHub minutes.  Also faster (no SSH — the
runner IS the VPS so file operations are local).

---

## How deploys work now

1. Push any commit to `main` branch
2. `.github/workflows/deploy.yml` triggers immediately
3. Job runs on `krexion-vps` runner (i.e. on the VPS itself)
4. Steps:
   - Checkout code into `/opt/krexion-runner/_work/…`
   - Rebuild `Krexion-User-Package.zip`
   - Local `rsync` → `/opt/krexion/` (excludes `.env`, caches, node_modules, etc.)
   - Disk-space self-heal (docker prune, stale caches)
   - `docker compose build --no-cache backend frontend`
   - `docker compose up -d backend frontend`
   - Health check + version report

Typical duration: **8-12 minutes** per full deploy.

---

## Monitoring the runner

**Check runner is online (from anywhere with the PAT):**
```bash
curl -s -H "Authorization: token <PAT>" \
  https://api.github.com/repos/krexion-com-final/krexion.com-final/actions/runners \
  | python3 -m json.tool
```
Look for `krexion-vps` with `"status": "online"`.

**On the VPS itself:**
```bash
systemctl status krexion-runner
# or fallback if the alias didn't get created:
systemctl status actions.runner.krexion-com-final-krexion.com-final.krexion-vps.service
```

**Tail runner logs:**
```bash
journalctl -u krexion-runner -f
# or:
tail -f /opt/krexion-runner/_diag/Runner_*.log
```

---

## What to do if the runner goes offline

1. **First: check the VPS is up + reachable.**  If the VPS itself
   is down, the runner will show `offline` in GitHub.  Fixing the
   VPS auto-restarts the runner.

2. **Runner service died on live VPS:**
   ```bash
   ssh <vps_user>@<vps_host>
   sudo systemctl restart krexion-runner
   sudo systemctl status krexion-runner  # confirm active
   ```

3. **Runner token expired / re-config needed:**
   Runner tokens rotate but the running service reuses its existing
   credentials indefinitely.  You should only need a fresh token if
   the runner's `.credentials` file is corrupted OR you deleted the
   runner from GitHub Settings.  In that case, re-bootstrap:

   a. On any machine with the PAT + repo write access:
      ```bash
      curl -s -X POST -H "Authorization: token <PAT>" \
        https://api.github.com/repos/krexion-com-final/krexion.com-final/actions/runners/registration-token
      ```
      Copy the `token` value.

   b. On the VPS:
      ```bash
      cd /opt/krexion-runner
      sudo ./svc.sh stop
      sudo ./svc.sh uninstall
      sudo -E RUNNER_ALLOW_RUNASROOT=1 ./config.sh remove --token <old-token>  # if it can reach GH
      sudo -E RUNNER_ALLOW_RUNASROOT=1 ./config.sh \
        --url https://github.com/krexion-com-final/krexion.com-final \
        --token <NEW-TOKEN-FROM-STEP-A> \
        --name krexion-vps \
        --labels self-hosted,linux,krexion-vps \
        --work _work \
        --unattended --replace
      sudo ./svc.sh install root
      sudo ./svc.sh start
      ```

---

## What about Windows builds?

`.github/workflows/build-windows-release.yml` and
`build-electron-desktop.yml` both use `runs-on: windows-latest`.
Those still consume GitHub Actions Windows minutes (which are 10x
more expensive on the free tier and reset separately from Linux
minutes).

**Options if Windows minutes exhaust too:**

- **Option A** — enable usage-based billing on the org. Rate for
  Windows: $0.016/min = ~$1.60 for a 100-min build. Set a
  spending limit at
  https://github.com/organizations/krexion-com-final/billing/summary
- **Option B** — set up a Windows self-hosted runner on any
  Windows 10/11 machine you own (dedicated workstation, home PC,
  etc.). Use `runs-on: [self-hosted, windows]` in the workflow.
  Bootstrap flow is identical to the Linux one above but with
  `actions-runner-win-x64-*.zip`.
- **Option C** — accept longer release cadence: only push to main
  when Windows quota is available (start of billing cycle) so
  installer builds succeed.

Recommended: **Option A** — simplest, cheapest, no VPS pollution.

---

## Adding a new collaborator?

Nothing to do — collaborators push to `main` as usual and the
deploy just works.  They don't need PAT / SSH / runner knowledge.
All they see is a green check in the Actions tab within ~10 min
of every push.

**Only exception:** if a collaborator's push includes a change to
`docker-compose.yml`, `Dockerfile.*`, `requirements.txt`, or
`package.json`, the docker rebuild step may take longer (up to
20 min) because layer caches are invalidated. That's expected.

---

## Runner cost / resource impact on the VPS

- Idle: ~30 MB RAM, 0 % CPU
- During deploy: ~1 GB RAM peak (docker build), 100 % of 1 CPU
  core for ~5 min while backend + frontend Dockerfiles run
- Disk: `_work/` dir grows over time (git checkouts).  The
  runner auto-cleans between jobs but if disk gets tight, wipe
  it manually: `rm -rf /opt/krexion-runner/_work/*`

The VPS was already sized for Krexion's production load; the
runner overhead is negligible.

---

## Security notes

- Runner runs as `root` on the VPS.  Same trust level as any
  Krexion deploy would have.  Only maintainers with commit
  access to the `main` branch can trigger deploys.
- `VPS_SSH_KEY` secret is retained in GitHub but no longer used
  by the deploy workflow.  Keep it — it's used by
  `.github/workflows/bootstrap-vps-runner.yml` if you ever need
  to re-bootstrap the runner from an external CI.
- Runner registration tokens auto-expire in ~1 hour.  The runner
  itself has a long-lived credential in
  `/opt/krexion-runner/.credentials` that survives GitHub-side
  runner token expiry.

---

## FAQ

**Q: Can I use `ubuntu-latest` again later?**
A: Yes — just change `runs-on: [self-hosted, krexion-vps]` back to
   `runs-on: ubuntu-latest` in `deploy.yml`. The old SSH-based
   deploy logic is in git history if you need to restore it.

**Q: Does the runner need internet access?**
A: Yes — it long-polls `https://api.github.com/actions/*` for
   incoming jobs. Standard outbound HTTPS is all it needs. If your
   firewall blocks outbound, allowlist `*.actions.githubusercontent.com`
   and `api.github.com`.

**Q: Can I run multiple parallel deploys?**
A: No — the `concurrency: krexion-vps-deploy` group in
   `deploy.yml` serializes deploys so a `docker compose build`
   never races with another `docker compose up`. Additional pushes
   during an in-flight deploy queue up cleanly.

**Q: What happens if the deploy job crashes mid-rebuild?**
A: The old containers keep running (docker compose up doesn't
   remove them until new images are ready). If build fails, next
   push retries from scratch. Zero downtime on failed deploys.
