#!/bin/bash -e
#
# WN-Turnip production build driver — produces both balanced (b) and
# performance (p) variants from latest upstream mesa main with the WinNative
# A8xx workaround set applied.
#
# Output ZIPs:
#   ../WN-Turnip-${BUILD_VERSION}-b_Axxx.zip
#   ../WN-Turnip-${BUILD_VERSION}-p_Axxx.zip

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$SCRIPT_DIR"

export BUILD_VERSION="1.0"
export EXTRA_PATCH=""
export EXTRA_SCRIPT="patches/fix_gralloc_flushall.py:patches/fix_a8xx_dev_info.py:patches/apply_a8xx_gpus.py:patches/apply_a7xx_gen1_quirks.py:patches/apply_a7xx_gen2_ubwc_hint.py:patches/disable_64b_image_atomics.py"

variants=(b p)

for variant in "${variants[@]}"; do
	echo ""
	echo "============================================"
	echo "  Building WN-Turnip-${BUILD_VERSION}-${variant}"
	echo "============================================"

	rm -rf turnip_workdir /tmp/turnip-main
	export BUILD_VARIANT="$variant"

	log_file="build_log_${variant}.txt"
	./build_turnip.sh 2>&1 | tee "$log_file"

	zipname="WN-Turnip-${BUILD_VERSION}-${variant}_Axxx.zip"
	cp "turnip_workdir/${zipname}" "./${zipname}" 2>/dev/null || true
	cp "./${zipname}" "${ROOT_DIR}/${zipname}" 2>/dev/null || true
done

echo ""
echo "============================================"
echo "  Build Summary"
echo "============================================"
for variant in "${variants[@]}"; do
	zipname="WN-Turnip-${BUILD_VERSION}-${variant}_Axxx.zip"
	echo "${variant}: $(ls -lh "${ROOT_DIR}/${zipname}" 2>/dev/null | awk '{print $5}' || echo 'MISSING')"
done
