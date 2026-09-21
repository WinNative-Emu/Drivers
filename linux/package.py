#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path
import subprocess
import sys

output, version, variant, commit, mesa_version = sys.argv[1:]
path = Path(output)
meta = {
    'schemaVersion': 1,
    'name': f'WN Linux Turnip {version}-{variant}',
    'description': 'Turnip for the WinNative glibc ARM64 GameScope/Wayland runtime',
    'author': 'WinNative',
    'platform': 'linux',
    'architecture': 'aarch64',
    'libc': 'glibc',
    'driverVersion': f'{version}-{variant}',
    'libraryName': 'libvulkan_freedreno.so',
    'variant': variant,
    'mesaVersion': mesa_version,
    'mesaCommit': commit,
    'mesaSource': 'https://gitlab.freedesktop.org/mesa/mesa',
    'buildCommit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
    'librarySha256': hashlib.sha256((path / 'libvulkan_freedreno.so').read_bytes()).hexdigest(),
}
(path / 'meta.json').write_text(json.dumps(meta, indent=2) + '\n')
