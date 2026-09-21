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
