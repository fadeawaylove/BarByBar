from barbybar.release_notes import (
    build_full_commit_lines,
    build_release_notes,
    build_summary_lines,
    parse_commit_lines,
)


def test_build_summary_lines_groups_commits_into_chinese_sections() -> None:
    commits = parse_commit_lines(
        [
            "a1b2c3d\tAdd fuzzy name search to session and dataset dialogs",
            "b2c3d4e\tTrack last opened session for startup restore",
            "c3d4e5f\tSwitch installer wizard to Simplified Chinese",
            "d4e5f6a\tFix legacy migration and enhance hover bar details",
        ]
    )

    summary = build_summary_lines(commits)

    assert any(line.startswith("- 会话与数据：") for line in summary)
    assert any(line.startswith("- 发布与安装：") for line in summary)
    assert any("Fix legacy migration and enhance hover bar details" in line for line in summary)


def test_release_notes_filter_out_release_commit_from_summary_and_full_list() -> None:
    commits = parse_commit_lines(
        [
            "1111111\tRelease v0.3.15",
            "2222222\tUse local Chinese installer language file",
        ]
    )

    summary = build_summary_lines(commits)
    full_list = build_full_commit_lines(commits)

    assert all("Release v0.3.15" not in line for line in summary)
    assert full_list == ["- Use local Chinese installer language file (`2222222`)"]


def test_release_notes_use_fallback_when_only_release_commit_exists() -> None:
    commits = parse_commit_lines(["1111111\tRelease v0.3.15"])

    notes = build_release_notes(
        tag="v0.3.15",
        compare_label="v0.3.14...v0.3.15",
        compare_url="https://github.com/example/repo/compare/v0.3.14...v0.3.15",
        commits=commits,
    )

    assert "本次版本主要为发版整理，未检测到独立功能提交。" in notes
    assert "## 完整提交" in notes
    assert "无可展示的独立功能提交" in notes


def test_release_notes_debug_payload_is_json_serializable() -> None:
    commits = parse_commit_lines(
        [
            "1111111\tRelease v0.3.17",
            "2222222\tFix release notes script import path",
        ]
    )

    notes = build_release_notes(
        tag="v0.3.17",
        compare_label="v0.3.16...v0.3.17",
        compare_url="https://github.com/example/repo/compare/v0.3.16...v0.3.17",
        commits=commits,
    )

    assert "Fix release notes script import path" in notes
    assert "v0.3.16...v0.3.17" in notes
