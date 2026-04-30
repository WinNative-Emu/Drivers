#!/usr/bin/env python3
"""
Apply slightly aggressive autotune for the -b (balance) variant.
Uses string replacement for reliability across Mesa versions.

Changes:
1. tu_autotune.cc: Raise drawcall threshold from 5 to 7
2. tu_autotune.cc: Reduce GMEM bandwidth multiplier from 11 to 10
"""

AUTOTUNE_FILE = "src/freedreno/vulkan/tu_autotune.cc"

with open(AUTOTUNE_FILE, "r") as f:
    content = f.read()

changes = False

# Raise drawcall threshold from 5 to 7
OLD_DC = "if (cmd_buffer->state.rp.drawcall_count > 5)"
NEW_DC = "if (cmd_buffer->state.rp.drawcall_count > 7)"
if OLD_DC in content:
    content = content.replace(OLD_DC, NEW_DC)
    changes = True
    print(f"  {AUTOTUNE_FILE}: raised drawcall threshold 5 -> 7")
elif "> 7)" in content:
    print(f"  {AUTOTUNE_FILE}: drawcall threshold already raised")

# Reduce GMEM bandwidth multiplier from 11 to 10
OLD_BW = "gmem_bandwidth = (gmem_bandwidth * 11 + total_draw_call_bandwidth) / 10;"
NEW_BW = "gmem_bandwidth = (gmem_bandwidth * 10 + total_draw_call_bandwidth) / 10;"
if OLD_BW in content:
    content = content.replace(OLD_BW, NEW_BW)
    changes = True
    print(f"  {AUTOTUNE_FILE}: reduced bandwidth multiplier 11 -> 10")
elif "* 10 + total" in content:
    print(f"  {AUTOTUNE_FILE}: bandwidth multiplier already reduced")

if changes:
    with open(AUTOTUNE_FILE, "w") as f:
        f.write(content)

print("apply_balance_variant.py: done")
