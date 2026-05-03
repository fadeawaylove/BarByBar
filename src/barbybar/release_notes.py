from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True)
class CommitEntry:
    sha: str
    subject: str


_RELEASE_SUBJECT = re.compile(r"^Release v\d+\.\d+\.\d+$", re.IGNORECASE)

_CATEGORY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("发布与安装", ("release", "installer", "setup", "github", "package", "wizard")),
    ("会话与数据", ("session", "database", "migration", "repository", "search", "dataset", "case", "legacy")),
    ("图表与交互", ("hover", "chart", "zoom", "shortcut", "bar", "trade", "crosshair", "drawing")),
    ("修复与兼容", ("fix", "error", "compat", "crash", "regression")),
)


def parse_commit_lines(lines: list[str]) -> list[CommitEntry]:
    entries: list[CommitEntry] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        sha, sep, subject = line.partition("\t")
        if not sep:
            continue
        entries.append(CommitEntry(sha=sha.strip(), subject=subject.strip()))
    return entries


def is_release_commit(subject: str) -> bool:
    return bool(_RELEASE_SUBJECT.match(subject.strip()))


def categorize_commit(subject: str) -> str:
    lowered = subject.lower()
    for category, keywords in _CATEGORY_RULES:
        if any(keyword in lowered for keyword in keywords):
            return category
    return "其他改动"


def build_summary_lines(commits: list[CommitEntry], *, max_items: int = 5) -> list[str]:
    filtered = [commit for commit in commits if not is_release_commit(commit.subject)]
    if not filtered:
        return ["- 本次版本主要为发版整理，未检测到独立功能提交。"]

    grouped: OrderedDict[str, list[str]] = OrderedDict()
    for commit in filtered:
        category = categorize_commit(commit.subject)
        grouped.setdefault(category, []).append(commit.subject)

    summary_lines: list[str] = []
    for category, subjects in grouped.items():
        unique_subjects = list(dict.fromkeys(subjects))
        summary_lines.append(f"- {category}：{'；'.join(unique_subjects)}。")
        if len(summary_lines) >= max_items:
            break
    return summary_lines


def build_full_commit_lines(commits: list[CommitEntry]) -> list[str]:
    filtered = [commit for commit in commits if not is_release_commit(commit.subject)]
    if not filtered:
        return ["- 无可展示的独立功能提交"]
    return [f"- {commit.subject} (`{commit.sha}`)" for commit in filtered]


def _displayable_commits(commits: list[CommitEntry]) -> list[CommitEntry]:
    return [commit for commit in commits if not is_release_commit(commit.subject)]


def build_release_notes(
    *,
    tag: str,
    compare_label: str,
    compare_url: str | None,
    commits: list[CommitEntry],
) -> str:
    lines: list[str] = ["## 本次改动", ""]
    lines.extend(build_summary_lines(commits))
    displayable_commits = _displayable_commits(commits)
    if len(displayable_commits) != 1:
        lines.extend(["", "## 完整提交", ""])
        lines.extend(build_full_commit_lines(commits))
    lines.extend(["", "## 版本信息", "", f"- 版本标签：{tag}"])
    if compare_url:
        lines.append(f"- 对比范围：[{compare_label}]({compare_url})")
    else:
        lines.append(f"- 对比范围：{compare_label}")
    return "\n".join(lines) + "\n"
