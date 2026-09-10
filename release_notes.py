#!/usr/bin/env python3
"""
Build the release notes for a WN-Turnip release.

Two changelogs matter for this driver and neither is derivable from the other:
the commits in this repository (what we changed about the build and the patch
set) and the commits in upstream Mesa between the previous release's driver and
this one (what changed underneath it). A Turnip regression is far more often
upstream's than ours, so the Mesa range has to be in the notes to be bisectable.

The Mesa commit a release was built from is recorded in the notes as an HTML
marker, so the next release can compute an exact range from it. Until a release
carries that marker the range falls back to the previous release's publish date,
which is close enough to bisect from.

Nothing here is allowed to fail the release: every network lookup degrades to a
note in the body.
"""
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

GITLAB = "https://gitlab.freedesktop.org/api/v4/projects/176"
MESA_WEB = "https://gitlab.freedesktop.org/mesa/mesa"
MARKER = "wn-mesa-commit"
MESA_PATHS = ["src/freedreno", "src/util/u_gralloc", "src/vulkan/runtime"]
MAX_LIST = 60

VERSION = os.environ.get("VERSION", "")
TAG = os.environ.get("TAG", "")
MESA_COMMIT = os.environ.get("MESA_COMMIT", "").strip()
MESA_VERSION = os.environ.get("MESA_VERSION", "").strip()
REPO = os.environ.get("REPO", "")
GH_TOKEN = os.environ.get("GH_TOKEN", "")
PREV_MESA_OVERRIDE = os.environ.get("PREV_MESA_COMMIT", "").strip()


def get_json(url, headers=None, timeout=60):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def gh(path):
    headers = {"Accept": "application/vnd.github+json"}
    if GH_TOKEN:
        headers["Authorization"] = f"Bearer {GH_TOKEN}"
    return get_json(f"https://api.github.com/repos/{REPO}{path}", headers)


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout.strip()


def previous_release():
    try:
        releases = gh("/releases?per_page=100")
    except Exception as exc:
        print(f"warning: could not list releases: {exc}", file=sys.stderr)
        return None
    published = [
        r for r in releases
        if not r.get("draft") and not r.get("prerelease")
        and re.fullmatch(r"v1\.\d{2}", r.get("tag_name", ""))
        and r.get("tag_name") != TAG
    ]
    if not published:
        return None
    published.sort(key=lambda r: [int(p) for p in r["tag_name"][1:].split(".")])
    return published[-1]


def mesa_commit_date(sha):
    if not sha:
        return None
    try:
        return get_json(f"{GITLAB}/repository/commits/{sha}")["created_at"]
    except Exception:
        return None


def mesa_compare(prev, cur):
    try:
        data = get_json(
            f"{GITLAB}/repository/compare?from={prev}&to={cur}&straight=true", timeout=120
        )
        return data.get("commits", [])
    except Exception as exc:
        print(f"warning: mesa compare failed: {exc}", file=sys.stderr)
        return None


def mesa_driver_commits(cur, since, until):
    seen, out = set(), []
    for path in MESA_PATHS:
        url = f"{GITLAB}/repository/commits?ref_name={cur}&path={path}&per_page=100"
        if since:
            url += f"&since={since}"
        if until:
            url += f"&until={until}"
        try:
            for c in get_json(url, timeout=120):
                if c["id"] not in seen:
                    seen.add(c["id"])
                    out.append(c)
        except Exception as exc:
            print(f"warning: mesa commits for {path} failed: {exc}", file=sys.stderr)
    out.sort(key=lambda c: c["created_at"], reverse=True)
    return out


def bullets(lines):
    if len(lines) <= MAX_LIST:
        return lines
    return lines[:MAX_LIST] + [f"- …and {len(lines) - MAX_LIST} more"]


prev = previous_release()
prev_tag = prev["tag_name"] if prev else None
prev_date = prev.get("published_at") if prev else None
prev_mesa = PREV_MESA_OVERRIDE or None
if not prev_mesa and prev and prev.get("body"):
    m = re.search(rf"{MARKER}:\s*([0-9a-f]{{40}})", prev["body"])
    if m:
        prev_mesa = m.group(1)

short = MESA_COMMIT[:9] if MESA_COMMIT else "unknown"
out = []

out.append(f"Turnip built from upstream Mesa main, packaged for Adrenotools.")
out.append("")
out.append(f"| | |")
out.append(f"|---|---|")
out.append(f"| Mesa | `{short}`" + (f" ({MESA_VERSION})" if MESA_VERSION else "") + " |")
out.append(f"| NDK | r26d |")
if prev_tag:
    out.append(f"| Previous release | [{prev_tag}](https://github.com/{REPO}/releases/tag/{prev_tag}) |")
out.append("")

out.append(f"## Driver changes since {prev_tag}" if prev_tag else "## Driver changes")
out.append("")
rng = f"{prev_tag}..HEAD" if prev_tag and git("tag", "-l", prev_tag) else ""
log = git("log", "--no-merges", "--pretty=format:%h\t%s", *( [rng] if rng else ["-20"] ))
if log:
    for line in log.splitlines():
        sha, _, subject = line.partition("\t")
        out.append(f"- {subject} (`{sha}`)")
    if not rng:
        out.append("")
        out.append(f"_({prev_tag} not present locally — showing the last 20 commits.)_" if prev_tag
                   else "_(no previous release — showing the last 20 commits.)_")
else:
    out.append("_No repository commits since the previous release; this is a Mesa-only refresh._")
out.append("")

out.append(f"## Mesa changes since {prev_tag}" if prev_tag else "## Mesa changes")
out.append("")
if not MESA_COMMIT:
    out.append("_The Mesa commit for this build was not recorded._")
else:
    cur_date = mesa_commit_date(MESA_COMMIT)
    if prev_mesa:
        commits = mesa_compare(prev_mesa, MESA_COMMIT)
        link = f"{MESA_WEB}/-/compare/{prev_mesa}...{MESA_COMMIT}"
        if commits is None:
            out.append(f"`{prev_mesa[:9]}` … `{short}` — [compare on GitLab]({link})")
        else:
            out.append(
                f"`{prev_mesa[:9]}` … `{short}` — **{len(commits)} commits** "
                f"([compare on GitLab]({link}))"
            )
        since = mesa_commit_date(prev_mesa)
    else:
        since = prev_date
        out.append(
            f"Built from `{short}` ([browse]({MESA_WEB}/-/commits/{MESA_COMMIT}))."
        )
        out.append("")
        out.append(
            "_The previous release did not record its Mesa commit, so the range below is "
            "bounded by its publish date instead. Releases from this one on carry an exact range._"
        )
    out.append("")
    driver = mesa_driver_commits(MESA_COMMIT, since, cur_date)
    out.append("### Turnip / freedreno commits in that range")
    out.append("")
    out.append(f"_Covers `{'`, `'.join(MESA_PATHS)}`._")
    out.append("")
    if driver:
        out.extend(bullets([
            f"- {c['title']} ([`{c['short_id']}`]({MESA_WEB}/-/commit/{c['id']}))"
            for c in driver
        ]))
    else:
        out.append("_None._")
out.append("")

out.append("## Variants")
out.append("")
out.append("| File | Tuning |")
out.append("|---|---|")
out.append(f"| `WN-Turnip-{VERSION}-b_Axxx.zip` | **Balanced.** Relaxed GMEM autotuner, "
           "standard KGSL power management. Best for most games and battery life. |")
out.append(f"| `WN-Turnip-{VERSION}-p_Axxx.zip` | **Performance.** Forces "
           "`KGSL_PROP_PWR_CONSTRAINT = PWR_MAX` at queue creation and re-asserts it every 1000 "
           "submissions. Higher framerate, higher power draw. |")
out.append("")
out.append("Both variants carry the full patch set, including the RedMagic green-screen fix for "
           "frame generation. Import via Container → Edit → Graphics Driver → Import driver.")
out.append("")
if MESA_COMMIT:
    out.append(f"<!-- {MARKER}: {MESA_COMMIT} -->")

print("\n".join(out))
