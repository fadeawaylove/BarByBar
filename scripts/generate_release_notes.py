from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from barbybar.release_notes import build_release_notes, parse_commit_lines


def _git_output(*args: str) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.splitlines()


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate release notes from git commits.")
    parser.add_argument("--tag", required=True)
    parser.add_argument("--repo-url", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    tag = args.tag.strip()
    all_tags = _git_output("tag", "--list", "v*", "--sort=-version:refname")
    previous_tag = next((item for item in all_tags if item.strip() and item.strip() != tag), "")
    compare_label = f"{previous_tag}...{tag}" if previous_tag else "首个版本发布"
    compare_url = f"{args.repo_url}/compare/{previous_tag}...{tag}" if previous_tag else None
    compare_range = f"{previous_tag}..{tag}" if previous_tag else tag
    commit_lines = _git_output("log", compare_range, r"--pretty=format:%h%x09%s")
    notes = build_release_notes(
        tag=tag,
        compare_label=compare_label,
        compare_url=compare_url,
        commits=parse_commit_lines(commit_lines),
    )

    output_path = Path(args.output)
    output_path.write_text(notes, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
