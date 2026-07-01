# Maintenance — patch review & upstream tracking

This repo always builds from **upstream mesa main**, then applies the idempotent
Python scripts in `patches/`. Because upstream moves, every patch must be able to
tell three states apart and act accordingly:

1. **Already applied** (our change is present) → log "already …", do nothing.
2. **Anchor present** (upstream unchanged) → apply the change.
3. **Anchor absent** (upstream refactored/absorbed it) → log a clear "anchor absent /
   upstream absorbed — skipping" line and exit 0. **Never** silently no-op, and
   **never** `sys.exit(1)` for an absorbed change (that would break the build).

All `patches/*.py` are idempotent and safe to re-run.

## Patch status — verified against mesa `43094891c9b` (Mesa 26.2.0-devel, 2026-07-01)

| Script | Target / anchor | Status | Notes |
|--------|-----------------|--------|-------|
| `fix_gralloc_flushall.py` | `u_gralloc_fallback.c` gmsm block | **needed** | UBWC detection for newer Qualcomm gralloc. Anchor present. |
| `fix_a8xx_dev_info.py` | `freedreno_dev_info.h` `disable_gmem` prop + `tu_cmd_buffer.cc` no_gmem check | **needed** | Upstream has render-pass-scoped `disable_gmem`, but **no per-GPU** flag. Anchor `bool has_image_processing;` present. |
| `apply_a8xx_gpus.py` | `freedreno_devices.py` A810 / A829 / A825 | **needed** | A810+A829 get `disable_gmem=True` + KGSL chip_ids; **A825 not upstream** (fully injected). |
| `apply_a7xx_gen1_quirks.py` | `a7xx_gen1` GPUProps | **needed** | Forces `has_early_preamble/has_scalar_predicates=False` for A720/725/730. |
| `apply_a7xx_gen2_ubwc_hint.py` | X1-85 / FD740 add_gpus block | **needed** | Adds `enable_tp_ubwc_flag_hint`. That block still lacks it upstream. |
| `disable_64b_image_atomics.py` | `has_64b_image_atomics = True` (×2, gen2+gen3) | **needed (workaround)** | UE5/VKD3D-Proton SM6.6 A8xx GPU-hang workaround. See removal criteria below. |
| `apply_balance_variant.py` (-b) | `tu_autotune.cc` drawcall + bandwidth | **partial** | Only the `*11→*10` bandwidth tweak lands; the `> 5` drawcall anchor was **removed upstream** (now `>= 10`) and is skipped. |
| `apply_perf_variant.py` (-p) | `tu_autotune.cc` + `tu_knl_kgsl.cc` PWR_MAX | **needed** | KGSL PWR_MAX clock-forcing anchors all present. Same autotune drawcall skip as -b. |

### Absorbed / removed by upstream (do NOT re-add)
- **`TU_DEBUG_FLUSHALL` forced for gen8** — upstream removed the forced flush from
  `tu_device.cc`. The old `fix_gralloc_flushall.py` half that stripped it is gone.
- **Autotune `drawcall_count > 5` gate** — restructured upstream to `>= 10`. The -b/-p
  scripts skip this tweak cleanly; the two variants now differ by **bandwidth + PWR_MAX**,
  not the drawcall threshold. (Re-target to the new gate only if a split is desired.)

### Removal criteria to watch on future bumps
- **`disable_64b_image_atomics.py`**: drop once upstream fixes the A8xx 64-bit image
  atomic implementation (track follow-ups to `5b87bbfad3b`). Until then, keep — the
  feature is still advertised `True` on gen2/gen3.
- **`apply_a8xx_gpus.py` A825 block**: drop the A825 insertion if upstream adds A825
  natively (the script already detects `name="Adreno (TM) 825"` / `FD825` and skips).
- **`fix_a8xx_dev_info.py`**: if upstream adds a per-device GMEM-disable mechanism,
  migrate A810/A829 to it and retire the custom `disable_gmem` prop.

## Re-verifying on a mesa bump
1. `BUILD_VERSION=<ver> ./build_wn_turnip.sh` (clones latest main, applies patches).
2. Read `build_log_{b,p}.txt`: every script should print an "applied" or an explicit
   "already/absent/skipping" line. A bare/missing line or a `WARNING:` means an anchor
   drifted — re-diff that script against current upstream before shipping.
3. Update the table above with the new mesa hash.

## Versioning

Releases use the scheme **`v1.NN`** — a two-digit, zero-padded counter after
`1.` (`v1.03`, `v1.04` … `v1.99`). The next version is **the latest published
`v1.NN` release + 1** (draft/prerelease releases are ignored); with no release
yet it floors at `1.03`. So `1.02` released → next `1.03`, `1.09` → `1.10`, etc.

The CI (`.github/workflows/build.yml`):
- **Weekly schedule** (`cron: '0 12 * * 3'`, Wednesdays 12:00 UTC, first run
  2026-07-08) builds `-b`/`-p` from latest mesa main and **tags + releases** the
  bumped version. Runs every week regardless of whether this repo changed, since
  mesa main advances on its own.
- **`workflow_dispatch`** does the same on demand.
- **PR / push** build a preview label only — never tag, never release.

Local builds set the label directly, e.g. `BUILD_VERSION=1.03 ./build_wn_turnip.sh`.

## Repository / contribution flow
This is developed on the fork **`maxjivi05/Drivers`** and contributed upstream to the
main repo **`WinNative-Emu/Drivers`** via pull request. Build/patch changes land on a
branch in the fork, then a PR is opened against `WinNative-Emu/Drivers:main`.
