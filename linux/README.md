# Linux ARM64 Turnip

Builds Mesa main for WinNative's glibc Linux runtime, with KGSL and Wayland/X11 presentation. This is separate from Android/bionic Adrenotools Turnip. It does not rebuild GameScope, Gallium, Zink or the rootfs's other Mesa components.

```sh
./build_linux_turnip.sh
```

On an ARM64 Linux host, install the dependencies listed in `.github/workflows/build-linux-turnip.yml`. Meson >=1.5, Python Mako/PyYAML, Ninja, C/C++ compilers, binutils, pkg-config, zip, flex, bison, glslang, and the Wayland/XCB/libdrm development packages are required. Mesa's checked-in wrap downloads verified Wayland protocols if the distro version is too old.

For a cross build using the existing WinNative Linux rootfs:

```sh
LINUX_SYSROOT=/absolute/path/to/rootfs ./build_linux_turnip.sh
```

The cross build additionally needs `aarch64-linux-gnu-gcc/g++`, ARM64 binutils and a host `wayland-scanner`. Rootfs development headers and pkg-config files must be available. `MESA_LOCAL_SRC` optionally supplies a Git checkout; both variants always use its HEAD. `BUILD_VERSION`, `BUILD_VARIANTS="b p"` and `BUILD_JOBS` control version, variants and parallelism. Build output is under `linux_work/`; distributable ZIPs are in the repository root.

Balanced (`-b`) uses the WN GPU fixes and GMEM bandwidth multiplier 10. Performance (`-p`) also requests KGSL PWR_MAX, sets the context/submission power-constraint flags, and refreshes the request every 1000 submissions. The upstream draw-call threshold was restructured; that retired tweak is deliberately skipped. Android gralloc/IMapper/AHB patches are excluded because this build uses glibc and Linux WSI.

`patch_mesa.py` ports the two WinNative `tools/linuxfs/turnip` fixes: KGSL dma-buf feedback device reporting, and disabling unsupported calibrated timestamps/present timing. It fails when its source anchors change. `verify_patches.py` also rejects warnings/missing patch anchors, aside from the retired draw-call threshold. Update and re-review patches when upstream changes; do not suppress failures to produce a release.

## ZIP contract

Each `WN-Linux-Turnip-<version>-{b,p}_Axxx.zip` contains a flat `meta.json` and `libvulkan_freedreno.so`. Metadata identifies `platform=linux`, `architecture=aarch64`, `libc=glibc`, `variant`, Mesa repository/SHA/version, build-recipe commit and SHA-256 of the library. The app creates its own ICD manifest after installing, so no device-specific absolute paths are distributed.

The `WN-Linux-` prefix reserves a separate catalog namespace. Linux releases use `linux-v...` tags and do not change the repository's latest Android release. Neither the Android mirror nor Android release notes are modified.

The app detects actual library ABI through ELF dependencies and corrects an Android/Linux destination mistake. Packages with contradictory platform metadata or an incorrect digest are rejected. New installs select that Linux driver; Settings can select another or return to bundled Mesa. The old Components/Linux Client driver remains separately available.

## Validation and provenance

The script verifies that all variants use one Mesa SHA, their binaries differ, they are ARM64/glibc libraries with Wayland and X11 entry points, and only `-p` contains the power-constraint code. CI uploads source diffs, patch logs, metadata and build logs along with separate variant artifacts. The app's package installation and UI tests run on AVD; rendering and KGSL power behavior require physical Adreno hardware.

Initial local validation built Mesa `5ff61a7646d29b54c324af0a60aa3bfb5cdd24d1`, version `26.3.0-devel`, against the existing Arch Linux ARM sysroot. Both variants passed package validation, and the Linux loader resolved the performance build's dependencies against that rootfs. Existing bundled Mesa 26.2.2 is preserved as fallback in the app.

## Release workflow

`build-linux-turnip.yml` builds both variants on Ubuntu 24.04 ARM64. Branch pushes build preview artifacts. Manual runs create a draft unless `publish` is true; scheduled runs publish. The cron is the same as the Android workflow: Wednesday 12:00 UTC (`0 12 * * 3`).

GitHub executes scheduled workflows only from the default branch. The feature branch's cron is not active by itself. To activate weekly builds, merge this workflow into the default branch or add a default-branch entrypoint that checks out the Linux branch. Preserve the Android workflow and its existing schedule. Manual dispatch also needs the workflow registered on the default branch; push builds work on this branch immediately.

A ready default-branch entrypoint is provided at `linux/scheduler/schedule-linux-turnip.yml`. Install that file as `.github/workflows/schedule-linux-turnip.yml` on `main` to call the reusable build from `feature/linux-drivers`. Its manual trigger defaults to a draft, while weekly runs publish. The reusable workflow checks out the Linux branch and records its actual recipe commit for release tags, even when the caller runs from main. Do not install both this scheduler and a separately scheduled copy of the full workflow on main.
