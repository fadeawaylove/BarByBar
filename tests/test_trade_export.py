from __future__ import annotations

import csv
from datetime import datetime
from io import StringIO
import json
from pathlib import Path

import pytest

from barbybar.domain.models import (
    DataSet,
    ReviewSession,
    SessionStats,
    SessionStatus,
    TradeEntryLeg,
    TradeReviewItem,
)
from barbybar import trade_export
from barbybar.trade_export import (
    CSV_EXPORT_FIELDS,
    TRADE_EXPORT_SCHEMA_VERSION,
    TradeExportError,
    build_session_trade_export,
    export_session_trade_data,
)


def _dataset() -> DataSet:
    return DataSet(
        id=7,
        display_name="IF 主连 1分钟",
        symbol="IF",
        timeframe="1m",
        source_path="internal/source.csv",
        total_bars=500,
        start_time=datetime(2025, 1, 1, 9, 0),
        end_time=datetime(2025, 1, 1, 15, 0),
    )


def _session() -> ReviewSession:
    return ReviewSession(
        id=12,
        dataset_id=7,
        symbol="IF",
        timeframe="1m",
        chart_timeframe="5m",
        start_index=20,
        current_index=120,
        current_bar_time=datetime(2025, 1, 1, 11, 0),
        status=SessionStatus.COMPLETED,
        title="早盘突破训练",
        notes="控制回撤",
        tags=["突破", "早盘"],
        stats=SessionStats(
            total_trades=1,
            wins=1,
            total_pnl=6.5,
            average_pnl=6.5,
            profit_factor=2.0,
            max_drawdown=-1.5,
            expectancy=6.5,
            long_trades=1,
            avg_holding_bars=4.0,
        ),
        created_at=datetime(2025, 1, 1, 8, 0),
        updated_at=datetime(2025, 1, 1, 11, 5),
    )


def _trade(number: int = 1) -> TradeReviewItem:
    return TradeReviewItem(
        trade_number=number,
        entry_time=datetime(2025, 1, 1, 9, 35),
        exit_time=datetime(2025, 1, 1, 9, 55),
        direction="long",
        quantity=2.0,
        entry_price=100.25,
        exit_price=103.5,
        pnl=6.5,
        entry_bar_index=7,
        exit_bar_index=11,
        holding_bars=4,
        exit_reason="take_profit",
        is_manual=False,
        had_stop_protection=True,
        had_adverse_add=False,
        is_planned=True,
        entry_note="等待确认后入场",
        review_note="执行符合计划",
        entry_legs=[
            TradeEntryLeg(
                bar_index=7,
                timestamp=datetime(2025, 1, 1, 9, 35),
                price=100.25,
                quantity=2.0,
                action_index=3,
                note="首笔",
            )
        ],
    )


def test_build_session_trade_export_uses_stable_user_fields() -> None:
    export = build_session_trade_export(_session(), _dataset(), [_trade()])

    payload = export.to_dict()
    assert payload["schema_version"] == TRADE_EXPORT_SCHEMA_VERSION
    assert list(payload) == ["schema_version", "session", "trades"]
    assert payload["session"]["case_id"] == 12
    assert payload["session"]["dataset_name"] == "IF 主连 1分钟"
    assert payload["session"]["chart_timeframe"] == "5m"
    assert payload["session"]["status"] == "completed"
    assert payload["session"]["tags"] == ["突破", "早盘"]
    assert payload["session"]["win_rate"] == 1.0
    assert "position_json" not in payload["session"]
    assert payload["trades"][0]["trade_number"] == 1
    assert payload["trades"][0]["direction"] == "long"
    assert payload["trades"][0]["entry_time"] == "2025-01-01T09:35:00"
    assert payload["trades"][0]["exit_reason"] == "take_profit"
    assert payload["trades"][0]["review_note"] == "执行符合计划"
    assert payload["trades"][0]["entry_legs"][0]["leg_number"] == 1
    assert "session_id" not in payload["trades"][0]


def test_build_session_trade_export_sorts_trades_by_trade_number() -> None:
    export = build_session_trade_export(_session(), _dataset(), [_trade(3), _trade(1), _trade(2)])

    assert [trade.trade_number for trade in export.trades] == [1, 2, 3]


def test_build_session_trade_export_supports_empty_trade_collection() -> None:
    session = _session()
    session.stats = SessionStats()

    export = build_session_trade_export(session, _dataset(), [])

    assert export.session.total_trades == 0
    assert export.trades == ()
    assert export.to_dict()["trades"] == []


def test_build_session_trade_export_rejects_mismatched_dataset() -> None:
    dataset = _dataset()
    dataset.id = 99

    with pytest.raises(ValueError, match="does not belong"):
        build_session_trade_export(_session(), dataset, [])


def test_export_session_trade_data_writes_deterministic_utf8_json(tmp_path: Path) -> None:
    export = build_session_trade_export(_session(), _dataset(), [_trade()])
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    result = export_session_trade_data(export, first, format="json")
    export_session_trade_data(export, second, format="JSON")

    assert result.path == first.resolve()
    assert result.format == "json"
    assert result.trade_count == 1
    assert result.size_bytes == first.stat().st_size
    assert first.read_bytes() == second.read_bytes()
    assert not first.read_bytes().startswith(b"\xef\xbb\xbf")
    payload = json.loads(first.read_text(encoding="utf-8"))
    assert payload == export.to_dict()
    assert "执行符合计划" in first.read_text(encoding="utf-8")


def test_export_session_trade_data_writes_stable_excel_friendly_csv(tmp_path: Path) -> None:
    export = build_session_trade_export(_session(), _dataset(), [_trade(2), _trade(1)])
    target = tmp_path / "trades.csv"

    result = export_session_trade_data(export, target, format="csv")

    raw = target.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    reader = csv.DictReader(StringIO(raw.decode("utf-8-sig")))
    rows = list(reader)
    assert tuple(reader.fieldnames or ()) == CSV_EXPORT_FIELDS
    assert [row["trade_number"] for row in rows] == ["1", "2"]
    assert all(row["case_id"] == "12" for row in rows)
    assert rows[0]["dataset_name"] == "IF 主连 1分钟"
    assert rows[0]["direction"] == "long"
    assert rows[0]["entry_note"] == "等待确认后入场"
    assert json.loads(rows[0]["entry_legs"])[0]["leg_number"] == 1
    assert result.trade_count == 2


def test_export_empty_session_csv_keeps_summary_row(tmp_path: Path) -> None:
    session = _session()
    session.stats = SessionStats()
    export = build_session_trade_export(session, _dataset(), [])
    target = tmp_path / "empty.csv"

    export_session_trade_data(export, target, format="csv")

    rows = list(csv.DictReader(StringIO(target.read_text(encoding="utf-8-sig"))))
    assert len(rows) == 1
    assert rows[0]["case_id"] == "12"
    assert rows[0]["total_trades"] == "0"
    assert rows[0]["trade_number"] == ""
    assert rows[0]["review_note"] == ""


def test_export_failure_preserves_existing_target_and_cleans_partial(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    export = build_session_trade_export(_session(), _dataset(), [_trade()])
    target = tmp_path / "trades.json"
    target.write_text("existing", encoding="utf-8")

    def fail_replace(_source: str | Path, _target: str | Path) -> None:
        raise OSError("forced replace failure")

    monkeypatch.setattr(trade_export.os, "replace", fail_replace)

    with pytest.raises(TradeExportError, match="forced replace failure"):
        export_session_trade_data(export, target, format="json")

    assert target.read_text(encoding="utf-8") == "existing"
    assert list(tmp_path.glob(".*.partial")) == []


def test_export_rejects_unsupported_format_without_creating_file(tmp_path: Path) -> None:
    target = tmp_path / "trades.xml"

    with pytest.raises(TradeExportError, match="Unsupported"):
        export_session_trade_data(
            build_session_trade_export(_session(), _dataset(), []),
            target,
            format="xml",
        )

    assert not target.exists()
