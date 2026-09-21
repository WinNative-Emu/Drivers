#!/usr/bin/env bash
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
cd "$here"
version=${BUILD_VERSION:-0.1.0}
[[ "$version" =~ ^[a-zA-Z0-9._-]+$ ]]
work="$here/linux_work"
mkdir -p "$work"
if [[ -z "${MESA_LOCAL_SRC:-}" ]]; then
  rm -rf "$work/upstream"
  git clone --depth=1 --branch main https://gitlab.freedesktop.org/mesa/mesa.git "$work/upstream"
  MESA_LOCAL_SRC="$work/upstream"
fi
source_dir=$(cd "$MESA_LOCAL_SRC" && pwd)
commit=$(git -C "$source_dir" rev-parse HEAD)
mesa_version=$(tr -d '[:space:]' < "$source_dir/VERSION")
printf '%s\n' "$commit" > "$work/mesa_commit.txt"
printf '%s\n' "$mesa_version" > "$work/mesa_version.txt"
read -ra variants <<< "${BUILD_VARIANTS:-b p}"
for variant in "${variants[@]}"; do
  [[ "$variant" == b || "$variant" == p ]]
  src="$work/mesa-$variant"
  rm -rf "$src" "$work/build-$variant" "$work/package-$variant"
  git clone --no-hardlinks --shared "$source_dir" "$src"
  git -C "$src" checkout --detach "$commit"
  (
    cd "$src"
    for script in fix_a8xx_dev_info apply_a8xx_gpus apply_a7xx_gen1_quirks apply_a7xx_gen2_ubwc_hint; do
      python3 "$here/patches/$script.py"
    done
    if [[ "$variant" == b ]]; then
      python3 "$here/patches/apply_balance_variant.py"
    else
      BUILD_VARIANT=p python3 "$here/patches/apply_perf_variant.py"
    fi
    python3 "$here/linux/patch_mesa.py"
  ) 2>&1 | tee "$work/patch-$variant.log"
  python3 "$here/linux/verify_patches.py" "$src" "$variant" "$work/patch-$variant.log"
  git -C "$src" diff --binary > "$work/mesa-$variant.patch"
  options=()
  if [[ -n "${LINUX_SYSROOT:-}" ]]; then
    rootfs=$(cd "$LINUX_SYSROOT" && pwd)
    cat > "$work/cross.ini" <<EOF
[binaries]
c = 'aarch64-linux-gnu-gcc'
cpp = 'aarch64-linux-gnu-g++'
ar = 'aarch64-linux-gnu-ar'
strip = 'aarch64-linux-gnu-strip'
pkg-config = 'pkg-config'
wayland-scanner = '/usr/bin/wayland-scanner'
[properties]
sys_root = '$rootfs'
pkg_config_libdir = '$rootfs/usr/lib/pkgconfig:$rootfs/usr/share/pkgconfig'
[built-in options]
c_args = ['--sysroot=$rootfs']
cpp_args = ['--sysroot=$rootfs']
c_link_args = ['--sysroot=$rootfs', '-L$rootfs/usr/lib']
cpp_link_args = ['--sysroot=$rootfs', '-L$rootfs/usr/lib']
[host_machine]
system = 'linux'
cpu_family = 'aarch64'
cpu = 'aarch64'
endian = 'little'
EOF
    options+=(--cross-file "$work/cross.ini")
  else
    [[ $(uname -m) == aarch64 ]]
  fi
  meson setup "$work/build-$variant" "$src" "${options[@]}" --buildtype release \
    -Dvulkan-drivers=freedreno -Dfreedreno-kmds=msm,kgsl -Dgallium-drivers= -Dplatforms=wayland,x11 \
    -Dopengl=false -Dgbm=disabled -Dglx=disabled -Degl=disabled -Dllvm=disabled -Dvulkan-layers= -Dtools= -Dvideo-codecs=
  ninja -j "${BUILD_JOBS:-4}" -C "$work/build-$variant" src/freedreno/vulkan/libvulkan_freedreno.so
  package="$work/package-$variant"
  mkdir -p "$package"
  strip_command=strip
  [[ -z "${LINUX_SYSROOT:-}" ]] || strip_command=aarch64-linux-gnu-strip
  "$strip_command" -o "$package/libvulkan_freedreno.so" "$work/build-$variant/src/freedreno/vulkan/libvulkan_freedreno.so"
  python3 "$here/linux/package.py" "$package" "$version" "$variant" "$commit" "$mesa_version"
  (cd "$package" && zip -9 "$here/WN-Linux-Turnip-$version-${variant}_Axxx.zip" meta.json libvulkan_freedreno.so)
done
python3 "$here/linux/verify_packages.py" "${variants[@]/#/$here/WN-Linux-Turnip-$version-}"
