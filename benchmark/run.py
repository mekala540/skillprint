"""Reproduce BENCHMARK.md: clone each pack in packs.txt and run skillprint on it.

    python benchmark/run.py            # writes benchmark/results.json
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from skillprint.scan import scan, HOOK_EVENTS_EVERY_ACTION

HERE = Path(__file__).parent


def main() -> int:
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        for line in (HERE / "packs.txt").read_text().splitlines():
            if not line.strip():
                continue
            repo, stars, star_source = line.split()
            dest = Path(tmp) / repo.replace("/", "_")
            subprocess.run(["git", "clone", "-q", "--depth", "1", f"https://github.com/{repo}.git", str(dest)], check=True)
            r = scan(dest)
            groups = r.hooks_by_config()
            main_hooks = next(iter(groups.values()), [])
            rows.append({
                "repo": repo, "stars": int(stars), "star_source": star_source,
                "footprint": r.footprint, "skills": len(r.skills),
                "upfront_tokens": r.upfront_tokens, "on_use_tokens": r.on_use_tokens,
                "hooks_main_config": len(main_hooks),
                "hooks_every_action": sum(1 for h in main_hooks if h.event.lower() in HOOK_EVENTS_EVERY_ACTION),
                "scripts": len(r.scripts), "findings": r.finding_counts(),
            })
            print(f"{repo:45} {r.footprint:6} {r.upfront_tokens:>7} tokens", file=sys.stderr)
    (HERE / "results.json").write_text(json.dumps(rows, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
