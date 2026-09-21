#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

hashes = set()
commits = set()
for value in sys.argv[1:]:
    archive = Path(value if value.endswith('.zip') else value + '_Axxx.zip')
    with zipfile.ZipFile(archive) as package:
        meta = json.loads(package.read('meta.json'))
        library = package.read(meta['libraryName'])
    if meta['name'] != f'WN Linux Turnip {meta["driverVersion"]}' or not meta['driverVersion'].endswith('-' + meta['variant']):
        raise SystemExit('Incorrect driver label')
    if meta['platform'] != 'linux' or meta['architecture'] != 'aarch64' or meta['libc'] != 'glibc':
        raise SystemExit('Incorrect package platform')
    digest = hashlib.sha256(library).hexdigest()
    if digest != meta['librarySha256'] or digest in hashes:
        raise SystemExit('Invalid or identical variant libraries')
    hashes.add(digest)
    commits.add(meta['mesaCommit'])
    with tempfile.NamedTemporaryFile() as file:
        file.write(library)
        file.flush()
        header = subprocess.check_output(['readelf', '-h', file.name], text=True)
        dynamic = subprocess.check_output(['readelf', '-d', file.name], text=True)
    if 'AArch64' not in header or '[libc.so.6]' not in dynamic or '[libc.so]' in dynamic:
        raise SystemExit('Incorrect ELF ABI')
    if b'vkCreateWaylandSurfaceKHR' not in library or b'vkCreateXcbSurfaceKHR' not in library:
        raise SystemExit('Missing Linux WSI')
    if (b'Failed to set initial PWR_MAX constraint' in library) != (meta['variant'] == 'p'):
        raise SystemExit('Incorrect power variant')
    print(f'{archive.name}: ARM64 glibc, Wayland/X11, {meta["variant"]}, Mesa {meta["mesaCommit"]}')
if len(commits) != 1:
    raise SystemExit('Variants use different Mesa commits')
