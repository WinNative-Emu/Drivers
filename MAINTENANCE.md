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

## Patch status — verified against mesa `29c5f0ad445` (Mesa 26.3.0-devel, 2026-08-30)

| Script | Target / anchor | Status | Notes |
|--------|-----------------|--------|-------|
| `fix_gralloc_flushall.py` | `u_gralloc_fallback.c` gmsm block | **needed, but now a fallback-only path** | UBWC detection for newer Qualcomm gralloc. Once `add_aimapper_gralloc.py` lands, the AIMapper backend is selected first on any device with an IMapper5 vendor HAL and this file is never reached. Kept in `EXTRA_SCRIPT` for devices that have no IMapper5 SP-HAL and still land on the fallback — upstream Leb-Sun drops it. Our copy only warns on a missing anchor, so it cannot fail a build. |
| `fix_a8xx_dev_info.py` | `freedreno_dev_info.h` `disable_gmem` prop + `tu_cmd_buffer.cc` no_gmem check | **needed** | Upstream has render-pass-scoped `disable_gmem`, but **no per-GPU** flag. Anchor `bool has_image_processing;` present. The injected block picks its reason field from `REASON_FIELDS` — upstream renamed `tu_render_pass_state::gmem_disable_reason` to `force_render_mode_reason` after 2026-08-26 and the old hardcoded name broke the build. |
| `apply_a8xx_gpus.py` | `freedreno_devices.py` A810 / A829 / A825 | **needed** | A810+A829 get `disable_gmem=True` + KGSL chip_ids; **A825 not upstream** (fully injected). |
| `apply_a7xx_gen1_quirks.py` | `a7xx_gen1` GPUProps | **needed** | Forces `has_early_preamble/has_scalar_predicates=False` for A720/725/730. |
| `apply_a7xx_gen2_ubwc_hint.py` | X1-85 / FD740 add_gpus block | **needed** | Adds `enable_tp_ubwc_flag_hint`. That block still lacks it upstream. |
| `disable_64b_image_atomics.py` | `has_64b_image_atomics = True` (×2, gen2+gen3) | **retired — not in `EXTRA_SCRIPT`** | Kept on disk as a one-line revert. See below. |
| `add_aimapper_gralloc.py` | new file + `u_gralloc.c` selection table, `u_gralloc.h` enum, `u_gralloc_internal.h`, `meson.build` | **needed** | Ported from [Leb-Sun/Drivers](https://github.com/Leb-Sun/Drivers) `Redmagic-11-Pro-fixes`. IMapper5 backend via SP-HAL; nothing like it upstream. The backend must keep filling every field of `u_gralloc_buffer_basic_info` — mesa `b3bb742f` added `alloc_size`/`layer_count` and `d850d2ef` consumes them. |
| `add_ubwc_swapchain_usage.py` | `vk_android.c` `vk_android_get_ahb_image_properties()` `ahb_usage_props` assignment; `vk_physical_device.h` struct tail; `tu_device.cc` after `supported_sync_types` | **needed** | Ported from [Leb-Sun/Drivers](https://github.com/Leb-Sun/Drivers) `Redmagic-11-Pro-fixes`. Value is driver-set (`ahb_vendor_usage_compressed`) so no Qualcomm constant lands in shared code. **Must stay at that assignment** — the output-chained `VkAndroidHardwareBufferUsageANDROID` is what distinguishes an allocation query from import validation; moving it into `vk_image_format_info_to_ahb_usage()` breaks AHB *import* for every linear buffer. |
| `apply_balance_variant.py` (-b) | `tu_autotune.cc` drawcall + bandwidth | **partial** | Only the `*11→*10` bandwidth tweak lands; the `> 5` drawcall anchor was **removed upstream** (now `>= 10`) and is skipped. |
| `apply_perf_variant.py` (-p) | `tu_autotune.cc` + `tu_knl_kgsl.cc` PWR_MAX | **needed** | KGSL PWR_MAX clock-forcing anchors all present. Same autotune drawcall skip as -b. |

### Absorbed / removed by upstream (do NOT re-add)
- **`TU_DEBUG_FLUSHALL` forced for gen8** — upstream removed the forced flush from
  `tu_device.cc`. The old `fix_gralloc_flushall.py` half that stripped it is gone.
- **Autotune `drawcall_count > 5` gate** — restructured upstream to `>= 10`. The -b/-p
  scripts skip this tweak cleanly; the two variants now differ by **bandwidth + PWR_MAX**,
  not the drawcall threshold. (Re-target to the new gate only if a split is desired.)

### Retired patches
- **`disable_64b_image_atomics.py`** — dropped from `EXTRA_SCRIPT` in 1.12. It cleared
  `has_64b_image_atomics` on `a7xx_gen2` **and** `a7xx_gen3` (which every A8xx inherits),
  which removes `VK_EXT_shader_image_atomic_int64` / `shaderImageInt64Atomics`. That is the
  feature upstream added in `5b87bbfad3b` specifically "for SM6.6 in vkd3d-proton", so with
  it off, VKD3D-Proton reports `Options9.AtomicInt64OnTypedResourceSupported = FALSE` and
  rejects any pipeline whose DXIL uses typed 64-bit image atomics — Hogwarts Legacy and
  FF VII Rebirth among them. 1.12-test builds with it removed were confirmed working on
  device. The script stays on disk: if the A8xx post-submit GPU hang it was written for
  returns, re-append `:patches/disable_64b_image_atomics.py` to `EXTRA_SCRIPT` in
  `build_wn_turnip.sh`.

### Removal criteria to watch on future bumps
- **`apply_a8xx_gpus.py` A825 block**: drop the A825 insertion if upstream adds A825
  natively (the script already detects `name="Adreno (TM) 825"` / `FD825` and skips).
- **`fix_a8xx_dev_info.py`**: if upstream adds a per-device GMEM-disable mechanism,
  migrate A810/A829 to it and retire the custom `disable_gmem` prop.

### Ported from Leb-Sun/Drivers

`add_aimapper_gralloc.py`, `patches/aimapper/u_gralloc_aimapper.c` and
`add_ubwc_swapchain_usage.py` come from
[`Leb-Sun/Drivers`](https://github.com/Leb-Sun/Drivers) branch `Redmagic-11-Pro-fixes`
(commits `2b38ba8` … `dfd7651`). They are carried verbatim — re-sync from that branch
rather than editing them here, so the two trees do not diverge.

The `-b`/`-p` variant scripts also took his three-state reporting change: a drifted KGSL
anchor used to print nothing at all, so a `-p` zip could ship with no PWR_MAX clock
forcing and the CI drift grep would find nothing to complain about.

## Re-verifying on a mesa bump
1. `BUILD_VERSION=<ver> ./build_wn_turnip.sh` (clones latest main, applies patches).
2. `./verify_patches.sh` — asserts every patch reported itself applied, per variant,
   and fails if the RedMagic display fixes or the `-p` PWR_MAX edits are missing from a
   log. CI runs the same script, so a green CI run means both archives really carry
   both fixes. It tolerates exactly one known-benign "anchor absent" line, the autotune
   drawcall gate upstream restructured away.
3. Read `build_log_{b,p}.txt`: every script should print an "applied" or an explicit
   "already/absent/skipping" line. A bare/missing line or a `WARNING:` means an anchor
   drifted — re-diff that script against current upstream before shipping.
4. Update the table above with the new mesa hash.

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
- **`workflow_dispatch`** takes a `publish` input, default **false**. Either way the
  release is created with both zips and generated notes attached; `publish=false` creates
  it as a **GitHub draft**, so no git tag exists until someone hits Publish, and the
  WinNative-Components mirror is skipped. Re-running a draft build deletes the previous
  draft for that tag first — GitHub allows several drafts to share a tag name, so without
  that they stack up. Only a publish is guarded against reusing a version, since only a
  publish is irreversible.
- **PR / push** build a preview label only — never tag, never release.

Local builds set the label directly, e.g. `BUILD_VERSION=1.03 ./build_wn_turnip.sh`.

## Release notes

`release_notes.py` builds the body. Two changelogs go in, and neither is derivable from
the other:

- **Driver changes** — `git log <prev tag>..HEAD` in this repo. Needs the release job to
  check out with `fetch-depth: 0`, which is why it does.
- **Mesa changes** — the range between the previous release's mesa commit and this one,
  via the GitLab compare API (project 176), plus the commits touching `src/freedreno`,
  `src/util/u_gralloc` and `src/vulkan/runtime` in that range. A Turnip regression is far
  more often upstream's than ours, so this is what makes one bisectable.

The mesa commit is recorded in the body as `<!-- wn-mesa-commit: <sha> -->` and read back
on the next release to get an exact range. A release without that marker falls back to the
previous release's publish date, which is what `v1.15` had to do — `v1.14` predates the
marker. Every network lookup degrades to a note rather than failing the release.

`build_wn_turnip.sh` clones mesa **once** and builds every variant from that tree. Cloning
per variant let upstream advance in between, so a release could ship a `-b` and a `-p` from
different mesa commits and the notes could only name one. The commit and version land in
`mesa_hash.txt` / `mesa_version.txt`, which CI reads into job outputs and uploads with the
build logs — the build clones `--depth=1` and never prints the sha, so it is otherwise
unrecoverable after the fact.

## Repository / contribution flow
This is developed on the fork **`maxjivi05/Drivers`** and contributed upstream to the
main repo **`WinNative-Emu/Drivers`** via pull request. Build/patch changes land on a
branch in the fork, then a PR is opened against `WinNative-Emu/Drivers:main`.
