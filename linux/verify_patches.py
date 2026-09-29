#!/usr/bin/env python3
from pathlib import Path
import sys

source, variant, logfile = sys.argv[1:]
log = Path(logfile).read_text()
for line in log.splitlines():
    if 'drawcall anchor absent' in line:
        continue
    if any(word in line.lower() for word in ('warning:', 'anchor absent', 'anchor not', 'skipping', 'fatal:')):
        raise SystemExit(f'Patch did not apply: {line}')
root = Path(source)
kgsl = (root / 'src/freedreno/vulkan/tu_knl_kgsl.cc').read_text()
autotune = (root / 'src/freedreno/vulkan/tu_autotune.cc').read_text()
device = (root / 'src/freedreno/vulkan/tu_device.cc').read_text()
if not (root / 'src/freedreno/vulkan/tu_mesh.cc').exists() or '.EXT_mesh_shader = tu_has_mesh_shader(device)' not in device:
    raise SystemExit('Missing mesh shader emulation')
ir3_nir = (root / 'src/freedreno/ir3/ir3_nir.c').read_text()
if 'ir3_nir_lower_half_subgroups' not in ir3_nir:
    raise SystemExit('Missing half-wave subgroups')
if 'ir3_nir_lower_cube_coord' not in ir3_nir:
    raise SystemExit('Missing cube coordinate sanitizing')
if 'SP_GFX_BINDLESS_INVALIDATE' not in (root / 'src/freedreno/vulkan/tu_cmd_buffer.h').read_text():
    raise SystemExit('Missing A8XX bindless invalidation')
if 'kgsl_bo_create_alias' not in kgsl:
    raise SystemExit('Missing command stream BO alias')
for marker in ('kgsl_ib_cache_take', 'kgsl_ib_cache_put', 'KGSL_IB_CACHE_MAX_BYTES', 'TU_KGSL_IB_CACHE'):
    if marker not in kgsl:
        raise SystemExit(f'Missing bounded IB cache: {marker}')
checks = ['has_local = device->has_master = true']
if variant == 'p':
    checks += ['wnturnip_set_pwr_max_constraint(', 'count % 1000 == 0', 'KGSL_CONTEXT_PWR_CONSTRAINT', 'KGSL_CMDBATCH_PWR_CONSTRAINT']
elif 'wnturnip_set_pwr_max_constraint(' in kgsl:
    raise SystemExit('Balanced driver contains performance power constraints')
for marker in checks:
    if marker not in kgsl:
        raise SystemExit(f'Missing patch marker: {marker}')
if variant == 'b' and 'gmem_bandwidth * 10 + total_draw_call_bandwidth' not in autotune:
    raise SystemExit('Missing balanced autotuner')
print(f'{variant}: Linux and variant patches verified')
