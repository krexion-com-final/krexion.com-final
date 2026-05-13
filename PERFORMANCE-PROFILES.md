# RealFlow — Performance Profiles (Auto-Tuning)

> **TL;DR**: RealFlow ka installer aapke PC ki RAM + CPU detect karke 5 profiles mein se best choose karta hai aur Mongo, Backend, Frontend, WSL, aur RUT browser farm — sab automatic tune karta hai. Aapko kuch nahi karna.

---

## 5 Performance Tiers

| Tier | RAM | RUT Concurrency | Mongo Cap | Backend Cap | Frontend Cap | WSL Memory |
|------|-----|-----------------|-----------|-------------|--------------|------------|
| 🐭 **MICRO** | ≤ 6 GB | 1 parallel | 512 MB | 1.5 GB | 128 MB | 4 GB |
| 🐢 **LOW** | 7-10 GB | 2 parallel | 1 GB | 2.5 GB | 192 MB | 5 GB |
| 🐎 **MID** | 11-16 GB | 4 parallel | 2 GB | 4 GB | 256 MB | 10 GB |
| 🦅 **HIGH** | 17-32 GB | 8 parallel | 4 GB | 8 GB | 384 MB | 20 GB |
| 🦁 **BEAST** | > 32 GB | 16 parallel | 8 GB | 16 GB | 512 MB | 32 GB |

**CPU ceiling**: Real concurrency = `min(tier, CPU_cores × 2)`. So a 4-core / 32 GB box gets HIGH tier (8 workers) capped to **8** (4×2), not 16.

---

## Real-World Expected Performance

| Tier | Visits per 5 min (RUT) | Form-fill / hour | Recommended workload |
|------|------------------------|------------------|----------------------|
| MICRO | ~15 visits | ~120 | 1 small campaign |
| LOW (Dynabook 8GB) | ~30 visits | ~250 | 1-2 campaigns |
| MID | ~80 visits | ~600 | 3-5 campaigns parallel |
| HIGH | ~200 visits | ~1500 | 10+ campaigns, CPI jobs |
| BEAST | ~500 visits | ~3500+ | Production server load |

---

## How It Works (Architecture)

```
PC Boot
   │
   ▼
[Install.bat / install-realflow.sh]
   │
   ▼
detect-hardware.ps1 / .sh   ◄── reads CIM (Win) / /proc/meminfo (Linux)
   │
   ├─► RAM total
   ├─► CPU logical cores
   └─► Free disk on system drive
   │
   ▼
TIER = MICRO | LOW | MID | HIGH | BEAST
   │
   ├─► Writes %USERPROFILE%\.wslconfig with right memory cap
   ├─► Picks docker-compose.<tier>.yml override
   └─► Starts stack with: docker compose -f docker-compose.yml -f docker-compose.<tier>.yml up -d
   │
   ▼
Backend container reads RUT_MAX_CONCURRENCY env var
   │
   ▼
real_user_traffic.py enforces hard ceiling — user can ask for 100 concurrent
but engine caps at the tier-tuned value, preventing OOM
```

---

## Files involved

| File | Role |
|------|------|
| `scripts/detect-hardware.ps1` | Windows: returns `Get-RealFlowProfile` object with all tuning values |
| `scripts/detect-hardware.sh` | Linux/macOS: emits `RF_*` env vars (use with `eval`) |
| `docker-compose.yml` | Base stack (Mongo + Backend + Frontend + optional Cloudflare Tunnel) |
| `docker-compose.micro.yml` | Override for ≤ 6 GB PCs |
| `docker-compose.lowram.yml` | Override for 7-10 GB PCs (Dynabook L50-G profile) |
| `docker-compose.mid.yml` | Override for 11-16 GB PCs |
| `docker-compose.high.yml` | Override for 17-32 GB PCs |
| `docker-compose.beast.yml` | Override for > 32 GB PCs / servers |
| `RealFlow-RETUNE.bat` | Windows: re-detect + re-apply tuning anytime |
| `RealFlow-RETUNE.sh` | Linux/macOS: same |

---

## Backend API Endpoint

Frontend Settings page calls this to show current tier + tuning:

```bash
curl http://localhost:8001/api/diagnostics/hardware-profile
```

**Response** (example on a 32 GB / 8-core machine):
```json
{
  "detected": {
    "total_ram_gb": 31,
    "cpu_cores": 8,
    "platform": "Linux"
  },
  "recommended_tier": "HIGH",
  "recommended_settings": {
    "rut_concurrency": 8,
    "mongo_mem_limit": "4g",
    "backend_mem_limit": "8g",
    "frontend_mem_limit": "384m",
    "wsl_memory": "20GB",
    "compose_override": "docker-compose.high.yml"
  },
  "applied": {
    "rut_concurrency": 8,
    "rut_mem_limit_mb": "7000",
    "matches_recommendation": true
  },
  "hint": "Backend is already running with the recommended tuning."
}
```

---

## Manual Override

Agar aap tier ko manually override karna chahte ho (e.g. testing on 16 GB but want to simulate 8 GB):

**Windows** — edit `C:\realflow\.env` aur add:
```
RUT_MAX_CONCURRENCY=2
RUT_MEM_LIMIT_MB=2048
```
Phir: `docker compose -f docker-compose.yml -f docker-compose.lowram.yml restart backend`

**Linux** — same `.env` change in `/opt/realflow/.env`, phir restart.

---

## Re-tune anytime

PC mein RAM badha do (e.g. 8 GB → 16 GB), ya RealFlow ko zyada powerful PC pe move karo — bas:

**Windows**: `RealFlow-RETUNE.bat` pe double-click

**Linux/macOS**: `sudo bash RealFlow-RETUNE.sh`

Script khud:
1. Naye hardware detect karega
2. Naya tier pick karega
3. `.wslconfig` (Windows) re-write karega
4. Stack stop + new compose override ke saath restart karega

---

## Troubleshooting

### "OOM Killed" message in `docker compose logs`
RAM kam pad rahi hai. Solution:
- Run `RealFlow-RETUNE.bat` — agar tier downgrade kare to apply karne do
- Ya manually `.env` mein `RUT_MAX_CONCURRENCY=1`, `RUT_MEM_LIMIT_MB=1024` set karo

### Frontend slow
`docker compose stats` se dekho. Agar frontend container CPU >80% par phasa hai:
- Production build use karo: `docker compose -f docker-compose.yml build frontend && docker compose up -d frontend` (already production-mode in compose)

### RUT visits per min kam aa rahe
- CPU bottleneck check karo: `docker compose stats backend`
- Agar CPU consistently 95%+ → tier upgrade karo (RAM bhi badhao)
- Network bottleneck check karo: `docker compose exec backend curl -w "%{time_total}\n" https://example.com`

### Want max performance, regardless of overall PC slowdown
Edit `docker-compose.<tier>.yml` directly:
```yaml
backend:
  environment:
    RUT_MAX_CONCURRENCY: "32"   # push beyond auto-tier
  mem_limit: 24g
```
Save karke `docker compose up -d` chala do.

---

## FAQ

**Q: Kya old 4 GB laptop pe chalega?**
A: Bilkul. MICRO tier mein 1 RUT worker, 512 MB Mongo. Slow lekin chalega. WSL 4 GB allocate karega — Windows ke liye baki bachega.

**Q: 64 GB server pe deploy karna ho to?**
A: BEAST tier auto-pick hoga. 16 parallel RUT workers, 16 GB backend RAM. Production-grade throughput.

**Q: Multiple users one server (multi-tenant)?**
A: BEAST tier handle kar lega 5-10 concurrent active users. Beyond that horizontal scale karo (multiple backend replicas with Mongo Atlas).

**Q: Cloud deployment (DigitalOcean, AWS) — kaun sa tier?**
A: Provider ki instance size pe depend karta hai:
- DO `s-2vcpu-4gb` → MICRO
- DO `s-4vcpu-8gb` → LOW
- DO `c-16` (16 GB) → MID
- AWS `t3.2xlarge` (32 GB) → HIGH
- AWS `m5.4xlarge` (64 GB) → BEAST

---

**Pro tip**: Customer ko bechte time tier ki performance number mention karo. E.g. "16 GB PC pe 80+ visits/min" — concrete numbers help sell.
