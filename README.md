# WinNative Turnip Drivers

A unified [Turnip](https://docs.mesa3d.org/drivers/freedreno.html) Vulkan driver build for **all Adreno GPUs on Android**, packaged as Adrenotools-compatible `.zip` archives. The build script always pulls upstream Mesa main, applies the patches in `patches/`, and produces two flavours of the same `libvulkan_freedreno.so`.

## Variants

| Variant | File | Tuning |
|---------|------|--------|
| Balanced | `WN-Turnip-<version>-b_Axxx.zip` | Slightly relaxed GMEM autotuner. Standard KGSL power management. Best for most games and battery life. |
| Performance | `WN-Turnip-<version>-p_Axxx.zip` | Aggressive GMEM autotuner. Forces `KGSL_PROP_PWR_CONSTRAINT = PWR_MAX` at queue creation and re-asserts it every 1000 submissions to keep the GPU at top clocks. Higher framerate, higher power draw. |

Each archive ships:

```
libvulkan_freedreno.so
meta.json
```

## RedMagic green-screen fix for frame generation

RedMagic devices running GameSpace's display enhancements — "Superior Pic Quality" upscaling and
**frame generation** — render a green screen, then black, on a stock Turnip build. The vendor
display block reads the application's swapchain buffers directly and requires them to be
UBWC-compressed, exactly as the proprietary Adreno driver allocates them. Turnip satisfied neither
half of that contract, and each half is a complete cause on its own.

This fix is the work of **[Leb-Sun](https://github.com/Leb-Sun)**, developed and device-confirmed on
RedMagic 11 Pro / Adreno 840 / Android 16 in
[`Leb-Sun/Drivers`](https://github.com/Leb-Sun/Drivers) branch `Redmagic-11-Pro-fixes`. It is carried
here verbatim as two patch scripts, applied through `EXTRA_SCRIPT` and therefore present in **both**
the `-b` and `-p` archives.

### 1. Turnip never requested a compressed allocation

`add_ubwc_swapchain_usage.py`

Android 16's Vulkan loader does not size swapchain buffers through
`vkGetSwapchainGrallocUsageXANDROID`. That chain is a legacy fallback for old drivers and returns
before it is ever consulted. The loader instead chains `VkAndroidHardwareBufferUsageANDROID` onto the
**output** of `vkGetPhysicalDeviceImageFormatProperties2` and uses whatever the driver writes there.

Mesa's shared AHB usage calculation carries no vendor bits at all, so Turnip answered `0x200`
(`GPU_FRAMEBUFFER`) where the proprietary driver answers `0x10000200`. Gralloc allocated linear
buffers, the vendor upscaler and frame generator had no compressed source to read, and the display
pipeline produced green.

The patch adds a driver-set `vk_physical_device::ahb_vendor_usage_compressed`, which Turnip populates
with `0x10000000` — AIDL `BufferUsage` VENDOR_MASK, bits 28–31, which Qualcomm gralloc reads as
"allocate UBWC-compressed". The value lives in the driver rather than in shared Vulkan code, so
drivers that leave it zero are unaffected.

Two constraints on that patch are load-bearing and must survive any re-anchoring:

- **The bit is added only at the `ahb_usage_props` assignment**, never inside
  `vk_image_format_info_to_ahb_usage()`. That function serves two callers with opposite needs:
  allocation ("what usage should a new buffer be created with", where UBWC is wanted) and import
  validation ("what usage does this image require", where demanding UBWC rejects every buffer that
  lacks it). The output-chained `VkAndroidHardwareBufferUsageANDROID` is the only signal that
  distinguishes the two — import paths never chain it. A build that moved the bit into that function
  produced 448 `nativeImportAhbToVulkan failed` errors and a black screen, because WinNative's
  X-server images are allocated `CPU_READ_OFTEN | CPU_WRITE_OFTEN` and are linear by necessity.
- **The bit is skipped whenever any CPU usage bit is set.** Gralloc cannot return a CPU-mappable
  compressed buffer. That guard also honours an explicit `VK_IMAGE_COMPRESSION_DISABLED_EXT` for
  free, since upstream expresses a refusal by adding `CPU_WRITE_RARELY`.

### 2. Turnip could not tell a compressed buffer from a linear one

`add_aimapper_gralloc.py` + `patches/aimapper/u_gralloc_aimapper.c`

A driver loaded into an ordinary application process cannot link `libui`, and a Mesa configured with
`-Dandroid-stub=true` pins `dep_android_ui` / `dep_android_mapper4` to `null_dep` without probing. Both
of Mesa's IMapper backends are therefore compiled out, and `u_gralloc` falls through to
`u_gralloc_fallback.c` — no YCbCr support, no real modifier, no dataspace, and UBWC inferred from a
private-handle offset that modern Qualcomm gralloc no longer writes. The three remaining backends all
require a legacy `hw_get_module` HAL, which current Qualcomm devices do not ship.

`libui` itself reaches the vendor mapper through `AIMapper_loadIMapper()`, a plain C entry point that
`android_load_sphal_library()` can resolve from a non-vendor process. This backend does that directly:
`dlopen`/`dlsym` only, no `libui`, no `libhidlbase`, no root. It is inserted into the backend selection
table after the `libui`-backed GRALLOC4 entry, so a platform build still prefers the upstream path, and
before the legacy backends, which on a modern device only ever find an empty AOSP stub. When it loads,
it logs `Using IMapper v5 stable-C API via SP-HAL`.

Beyond restoring correct buffer metadata, it resolves one Qualcomm-specific layout mismatch. QTI's
mapper describes a UBWC buffer as **two** planes with the metadata plane first, at offset 0, and the
pixel data after it — measured on Adreno 840, 1216×2688 RGBA8888:

```
plane[0]  offset=86016  stride=4864   <- pixel data (4864 = 1216 * 4)
plane[1]  offset=0      stride=128    <- UBWC metadata (128 * 672 = 86016)
```

Mesa's generic path treats any plane after the first sitting at offset 0 as a separate allocation and
rejects the buffer as disjoint. The backend collapses this to the single
`DRM_FORMAT_MOD_QCOM_COMPRESSED` plane Mesa expects and Turnip already lays out correctly. Compression
is detected through the standard, vendor-neutral `StandardMetadataType::COMPRESSION` query, with the
plane-layout signature retained as a fallback because QTI's mapper has been observed reporting
`modifier=LINEAR` and `fourcc=0` on a demonstrably UBWC allocation.

### Verifying it on device

`aimapper: compressed layout detected via … collapsing to 1 compressed plane` in logcat is the single
observable sign that the whole UBWC path fired. Without it, a driver that quietly fell back to linear
buffers is indistinguishable from a working one except by looking at the screen, which reads the same
for several unrelated faults.

## Supported GPUs

A single driver covers the full Adreno line:

- **A6xx** — A6xx series (e.g. A640 / A650 / A660)
- **A7xx**
  - `gen1` — A720 / A725 / A730 (preamble + scalar-predicate quirks applied)
  - `gen2` — FD740 / Adreno X1-85 (UBWC hint applied to fix UI corruption)
  - `gen3` — A750 and later
- **A8xx** — A810 / A825 / A829 / A830 / A840 (and X2-85)
  - A810 / A829 boot with `disable_gmem` so they fall back to sysmem rendering (broken GMEM on those parts).
  - A825 (not yet upstream) is added with corrected tile geometry and depth-cache layout.
  - A830 / A840 / X2-85 use the upstream profiles unchanged.

## Features

- Always built from **upstream Mesa main** — every run re-clones, re-patches, re-builds. No pinned forks.
- Per-chip `disable_gmem` GPU property plumbed through `freedreno_dev_info.h` and `tu_cmd_buffer.cc` for parts with broken GMEM.
- KGSL UBWC gralloc detection bypass for devices that still land on the fallback backend (newer Qualcomm gralloc no longer writes the legacy `gmsm` magic header).
- `EXT_shader_image_atomic_int64` advertised as upstream intends, so VKD3D-Proton exposes `AtomicInt64OnTypedResourceSupported` and D3D12 titles needing SM6.6 typed 64-bit atomics (Hogwarts Legacy, FF VII Rebirth) run.
- Adrenotools-compatible `meta.json` with simple `WN-<version>-<variant>` driver versioning.

## Build

Requirements:

- Linux host (Ubuntu / Debian recommended)
- `git`, `meson`, `ninja`, `patchelf`, `unzip`, `curl`, `pip`, `flex`, `bison`, `zip`, `glslang` / `glslangValidator`
- Python with `mako`
- Android NDK r26d (the script expects it at `/home/max/Build/Turnip/android-ndk-r26d` — edit `build_turnip.sh` to point at your NDK)

```bash
./build_wn_turnip.sh
```

Outputs both variants as `WN-Turnip-<version>-{b,p}_Axxx.zip` in the project root.

Then confirm every patch actually landed. A patch script whose anchor drifted against upstream Mesa
logs a warning and continues, so the archive still builds and installs — it is simply missing the fix.
Only the build log shows that, and CI runs the same check:

```bash
./verify_patches.sh
```

## Install on device

Adrenotools-aware launchers (e.g. WinNative, Winlator) can import each `.zip` directly:

> Container → Edit → Graphics Driver → Import driver → pick the `.zip` → save → relaunch.

## Layout

```
.
├── build_wn_turnip.sh        # entrypoint: builds both -b and -p
├── build_turnip.sh           # core cross-compile engine (do not call directly)
├── verify_patches.sh         # asserts every patch reported applied, per variant
├── release_notes.py          # driver + Mesa changelogs for a release body
├── patches/
│   ├── add_aimapper_gralloc.py
│   ├── add_ubwc_swapchain_usage.py
│   ├── aimapper/u_gralloc_aimapper.c
│   ├── fix_gralloc_flushall.py
│   ├── fix_a8xx_dev_info.py
│   ├── apply_a8xx_gpus.py
│   ├── apply_a7xx_gen1_quirks.py
│   ├── apply_a7xx_gen2_ubwc_hint.py
│   ├── apply_balance_variant.py
│   ├── apply_perf_variant.py
│   └── disable_64b_image_atomics.py
├── MAINTENANCE.md            # per-patch upstream status + re-verify checklist
└── LICENSE
```

## Upstream & contributing

Development happens on the fork [`maxjivi05/Drivers`](https://github.com/maxjivi05/Drivers)
and is contributed to the main repo
[`WinNative-Emu/Drivers`](https://github.com/WinNative-Emu/Drivers) via pull request.
Because the build always tracks upstream Mesa main, the `patches/` scripts are written
to adapt as upstream changes — see [`MAINTENANCE.md`](MAINTENANCE.md) for each patch's
current status, what upstream has absorbed, and how to re-verify on a Mesa bump.

## Credits

The RedMagic green-screen fix for frame generation — the IMapper5 SP-HAL gralloc backend and the
UBWC swapchain usage bit — is the work of **[Leb-Sun](https://github.com/Leb-Sun)**, researched,
implemented and device-confirmed in [`Leb-Sun/Drivers`](https://github.com/Leb-Sun/Drivers) branch
`Redmagic-11-Pro-fixes`. Ported here with thanks; the diagnosis above is his.

## License

MIT — see `LICENSE`.

## Linux GameScope/Wayland drivers

The `feature/linux-drivers` branch adds glibc ARM64 Turnip packages alongside the existing Android builds. See [linux/README.md](linux/README.md) for the build, package format, validation and scheduling requirements. Android build scripts and releases keep their existing behavior.
