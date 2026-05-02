from __future__ import annotations

import argparse
import json
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


def _write_stdout(text: str) -> None:
    data = f"{text}\n".encode("utf-8", errors="replace")
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is not None:
        buffer.write(data)
        buffer.flush()
        return
    sys.stdout.write(data.decode("utf-8", errors="replace"))
    sys.stdout.flush()


def _first_non_empty(lines: list[str], *, exclude: str = "") -> str:
    excluded = exclude.strip()
    return next((item.strip() for item in lines if item.strip() and item.strip() != excluded), "")


def build_release_notes_from_git(
    *,
    tag: str,
    repo_url: str,
    previous_tag: str | None = None,
    head_ref: str | None = None,
    compare_label: str | None = None,
    compare_url: str | None = None,
) -> tuple[str, dict[str, object]]:
    normalized_tag = tag.strip()
    normalized_previous_tag = previous_tag.strip() if previous_tag is not None else None
    normalized_head_ref = (head_ref or normalized_tag).strip()
    if not normalized_tag:
        raise ValueError("--tag must not be empty.")
    if not normalized_head_ref:
        raise ValueError("--head-ref must not be empty when provided.")

    all_tags = _git_output("tag", "--list", "v*", "--sort=-version:refname")
    if normalized_previous_tag is None:
        normalized_previous_tag = _first_non_empty(all_tags, exclude=normalized_tag)

    resolved_compare_label = compare_label
    if resolved_compare_label is None:
        resolved_compare_label = f"{normalized_previous_tag}...{normalized_tag}" if normalized_previous_tag else "首个版本发布"

    resolved_compare_url = compare_url
    if resolved_compare_url is None and normalized_previous_tag:
        resolved_compare_url = f"{repo_url}/compare/{normalized_previous_tag}...{normalized_tag}"

    compare_range = f"{normalized_previous_tag}..{normalized_head_ref}" if normalized_previous_tag else normalized_head_ref
    commit_lines = _git_output("log", compare_range, r"--pretty=format:%h%x09%s")
    notes = build_release_notes(
        tag=normalized_tag,
        compare_label=resolved_compare_label,
        compare_url=resolved_compare_url,
        commits=parse_commit_lines(commit_lines),
    )
    debug_payload: dict[str, object] = {
        "tag": normalized_tag,
        "previous_tag": normalized_previous_tag,
        "head_ref": normalized_head_ref,
        "compare_range": compare_range,
        "compare_label": resolved_compare_label,
        "compare_url": resolved_compare_url,
        "commit_lines": commit_lines,
    }
    return notes, debug_payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate release notes from git commits.")
    parser.add_argument("--tag", required=True)
    parser.add_argument("--repo-url", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--previous-tag", default=None, help="Previous version tag. Omit to auto-detect; pass an empty string for first-release notes.")
    parser.add_argument("--head-ref", default=None, help="Git ref to use as the end of the commit range. Defaults to --tag.")
    parser.add_argument("--compare-label", default=None)
    parser.add_argument("--compare-url", default=None)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    notes, debug_payload = build_release_notes_from_git(
        tag=args.tag,
        repo_url=args.repo_url,
        previous_tag=args.previous_tag,
        head_ref=args.head_ref,
        compare_label=args.compare_label,
        compare_url=args.compare_url,
    )

    output_path = None if args.output == "-" else Path(args.output)
    if output_path is None:
        _write_stdout(notes.rstrip())
    else:
        output_path.write_text(notes, encoding="utf-8")
    if args.verbose:
        debug_payload["output_path"] = str(output_path) if output_path is not None else "-"
        _write_stdout("RELEASE_NOTES_DEBUG_START")
        _write_stdout(json.dumps(debug_payload, ensure_ascii=False, indent=2))
        _write_stdout("RELEASE_NOTES_MARKDOWN_START")
        _write_stdout(notes)
        _write_stdout("RELEASE_NOTES_MARKDOWN_END")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
