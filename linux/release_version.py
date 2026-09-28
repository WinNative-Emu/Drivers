#!/usr/bin/env python3
import json
import re
import sys


def next_version(releases):
    versions = []
    for release in releases:
        match = re.fullmatch(r'linux-v(\d+)\.(\d+)\.(\d+)', release['tag_name'])
        if match and not release['draft'] and not release['prerelease']:
            versions.append(tuple(map(int, match.groups())))
    if not versions:
        return '0.1.0'
    major, minor, patch = max(versions)
    return '.'.join(map(str, max((0, 1, 0), (major, minor, patch + 1))))


if __name__ == '__main__':
    print(next_version([release for page in json.load(sys.stdin) for release in page]))
