from barbybar.release_notes import (
    build_full_commit_lines,
    build_release_notes,
    build_summary_lines,
    parse_commit_lines,
)


def _load_generate_release_notes_module():
    import importlib.util
    from pathlib import Path

    script_path = Path(__file__).resolve().parents[1] / "scripts" / "generate_release_notes.py"
    spec = importlib.util.spec_from_file_location("generate_release_notes_for_test", script_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


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


def test_release_notes_omit_full_commit_section_for_single_feature_commit() -> None:
    commits = parse_commit_lines(["290b39c\t修复历史交易定位k线图不准"])

    notes = build_release_notes(
        tag="v0.5.20",
        compare_label="v0.5.19...v0.5.20",
        compare_url="https://github.com/example/repo/compare/v0.5.19...v0.5.20",
        commits=commits,
    )

    assert "## 本次改动" in notes
    assert "修复历史交易定位k线图不准" in notes
    assert "## 完整提交" not in notes
    assert "(`290b39c`)" not in notes


def test_release_notes_keep_full_commit_section_for_multiple_feature_commits() -> None:
    commits = parse_commit_lines(
        [
            "1111111\tFix release notes script import path",
            "2222222\tImprove trade history review workflow",
        ]
    )

    notes = build_release_notes(
        tag="v0.5.20",
        compare_label="v0.5.19...v0.5.20",
        compare_url=None,
        commits=commits,
    )

    assert "## 完整提交" in notes
    assert "- Fix release notes script import path (`1111111`)" in notes
    assert "- Improve trade history review workflow (`2222222`)" in notes


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


def test_trade_review_workflow_commit_is_not_misclassified_as_release_workflow() -> None:
    commits = parse_commit_lines(["f6928b1\tImprove trade history review workflow"])

    summary = build_summary_lines(commits)

    assert summary == ["- 图表与交互：Improve trade history review workflow。"]


def test_generate_release_notes_supports_future_tag_preview(monkeypatch) -> None:
    module = _load_generate_release_notes_module()
    git_calls: list[tuple[str, ...]] = []

    def fake_git_output(*args: str) -> list[str]:
        git_calls.append(args)
        if args[:3] == ("tag", "--list", "v*"):
            return ["v0.5.13"]
        if args[0] == "log":
            assert args[1] == "v0.5.13..HEAD"
            return ["f6928b1\tImprove trade history review workflow", "1111111\tRelease v0.5.14"]
        raise AssertionError(args)

    monkeypatch.setattr(module, "_git_output", fake_git_output)

    notes, debug = module.build_release_notes_from_git(
        tag="v0.5.14",
        repo_url="https://github.com/example/BarByBar",
        previous_tag="v0.5.13",
        head_ref="HEAD",
    )

    assert debug["compare_range"] == "v0.5.13..HEAD"
    assert debug["compare_label"] == "v0.5.13...v0.5.14"
    assert "Improve trade history review workflow" in notes
    assert "Release v0.5.14" not in notes
    assert git_calls


def test_generate_release_notes_reads_git_output_as_utf8(monkeypatch) -> None:
    module = _load_generate_release_notes_module()
    calls: list[dict[str, object]] = []

    class Result:
        stdout = "290b39c\t修复历史交易定位k线图不准\n"

    def fake_run(*args, **kwargs):  # noqa: ANN001
        calls.append(kwargs)
        return Result()

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    assert module._git_output("log", "HEAD", r"--pretty=format:%h%x09%s") == ["290b39c\t修复历史交易定位k线图不准"]
    assert calls[0]["encoding"] == "utf-8"
    assert calls[0]["errors"] == "replace"


def test_generate_release_notes_preserves_existing_tag_based_behavior(monkeypatch) -> None:
    module = _load_generate_release_notes_module()

    def fake_git_output(*args: str) -> list[str]:
        if args[:3] == ("tag", "--list", "v*"):
            return ["v0.5.14", "v0.5.13"]
        if args[0] == "log":
            assert args[1] == "v0.5.13..v0.5.14"
            return ["2222222\tFix release notes script import path"]
        raise AssertionError(args)

    monkeypatch.setattr(module, "_git_output", fake_git_output)

    notes, debug = module.build_release_notes_from_git(
        tag="v0.5.14",
        repo_url="https://github.com/example/BarByBar",
    )

    assert debug["previous_tag"] == "v0.5.13"
    assert debug["head_ref"] == "v0.5.14"
    assert "v0.5.13...v0.5.14" in notes
    assert "Fix release notes script import path" in notes


def test_generate_release_notes_supports_first_release_preview(monkeypatch) -> None:
    module = _load_generate_release_notes_module()

    def fake_git_output(*args: str) -> list[str]:
        if args[:3] == ("tag", "--list", "v*"):
            return []
        if args[0] == "log":
            assert args[1] == "HEAD"
            return ["3333333\tAdd first public release workflow"]
        raise AssertionError(args)

    monkeypatch.setattr(module, "_git_output", fake_git_output)

    notes, debug = module.build_release_notes_from_git(
        tag="v0.1.0",
        repo_url="https://github.com/example/BarByBar",
        previous_tag="",
        head_ref="HEAD",
    )

    assert debug["previous_tag"] == ""
    assert debug["compare_label"] == "首个版本发布"
    assert debug["compare_url"] is None
    assert "首个版本发布" in notes
    assert "Add first public release workflow" in notes


def test_generate_release_notes_can_write_to_stdout_without_output_file(monkeypatch, capsys) -> None:
    module = _load_generate_release_notes_module()

    def fake_build_release_notes_from_git(**kwargs):
        return "## 本次改动\n\n- 测试发布说明。\n", {"tag": kwargs["tag"]}

    monkeypatch.setattr(module, "build_release_notes_from_git", fake_build_release_notes_from_git)

    result = module.main.__wrapped__ if hasattr(module.main, "__wrapped__") else None
    assert result is None

    monkeypatch.setattr(
        "sys.argv",
        [
            "generate_release_notes.py",
            "--tag",
            "v0.5.14",
            "--repo-url",
            "https://github.com/example/BarByBar",
            "--output",
            "-",
        ],
    )

    assert module.main() == 0
    assert "测试发布说明" in capsys.readouterr().out
