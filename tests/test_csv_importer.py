from pathlib import Path
import shutil
from datetime import datetime
from uuid import uuid4

import pytest

from barbybar.data.csv_importer import (
    CsvQualityCode,
    MissingColumnsError,
    infer_symbol_from_filename,
    inspect_csv,
    load_bars_from_csv,
)


def test_import_standard_csv() -> None:
    result = load_bars_from_csv(Path("sample_data/if_sample.csv"))
    assert len(result.bars) == 10
    assert result.bars[0].open == 3860.0
    assert result.bars[-1].close == 3884.0


def test_inspect_csv_returns_mapping_samples_count_and_time_range() -> None:
    result = inspect_csv(Path("sample_data/if_sample.csv"), sample_limit=3)

    assert result.detected_columns == ("datetime", "open", "high", "low", "close", "volume")
    assert result.suggested_mapping == {
        "datetime": "datetime",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "volume": "volume",
    }
    assert len(result.sample_rows) == 3
    assert result.sample_rows[0].row_number == 2
    assert result.sample_rows[0].values[0] == "2025-01-02 09:30:00"
    assert result.valid_row_count == 10
    assert result.duplicates_removed == 0
    assert result.start_time == datetime(2025, 1, 2, 9, 30)
    assert result.end_time == datetime(2025, 1, 2, 9, 39)


def test_inspect_csv_is_read_only_and_uses_explicit_mapping(tmp_path: Path) -> None:
    csv_path = tmp_path / "custom.csv"
    csv_path.write_text(
        "Time,OpenPx,HighPx,LowPx,ClosePx,Vol\n"
        "2025-01-01 09:00,1,2,0.5,1.5,10\n",
        encoding="utf-8",
    )
    database_path = tmp_path / "barbybar.db"

    result = inspect_csv(
        csv_path,
        field_map={
            "datetime": "Time",
            "open": "OpenPx",
            "high": "HighPx",
            "low": "LowPx",
            "close": "ClosePx",
            "volume": "Vol",
        },
    )

    assert result.valid_row_count == 1
    assert result.suggested_mapping["close"] == "ClosePx"
    assert result.sample_rows[0].values == (
        "2025-01-01 09:00",
        "1",
        "2",
        "0.5",
        "1.5",
        "10",
    )
    assert database_path.exists() is False


def test_inspect_csv_reports_importable_rows_after_deduplication(tmp_path: Path) -> None:
    csv_path = tmp_path / "unordered-duplicates.csv"
    csv_path.write_text(
        "datetime,open,high,low,close,volume\n"
        "2025-01-01 09:02,2,3,1,2.5,20\n"
        "2025-01-01 09:01,1,2,0.5,1.5,10\n"
        "2025-01-01 09:02,4,5,3,4.5,30\n",
        encoding="utf-8",
    )

    result = inspect_csv(csv_path, sample_limit=2)

    assert result.valid_row_count == 2
    assert result.duplicates_removed == 1
    assert result.start_time == datetime(2025, 1, 1, 9, 1)
    assert result.end_time == datetime(2025, 1, 1, 9, 2)
    assert [row.row_number for row in result.sample_rows] == [2, 3]


def test_inspect_csv_rejects_negative_sample_limit() -> None:
    with pytest.raises(ValueError, match="sample_limit"):
        inspect_csv(Path("sample_data/if_sample.csv"), sample_limit=-1)


def test_inspect_csv_reports_missing_required_fields_without_raising(tmp_path: Path) -> None:
    csv_path = tmp_path / "missing.csv"
    csv_path.write_text(
        "datetime,open,high,low,close\n"
        "2025-01-01 09:00,1,2,0.5,1.5\n",
        encoding="utf-8",
    )

    result = inspect_csv(csv_path)

    finding = next(item for item in result.quality_findings if item.code is CsvQualityCode.MISSING_REQUIRED_FIELDS)
    assert finding.count == 1
    assert finding.examples[0].field == "volume"
    assert result.suggested_mapping["datetime"] == "datetime"
    assert result.valid_row_count == 0
    assert result.start_time is None
    assert result.end_time is None


def test_inspect_csv_collects_datetime_and_numeric_parse_failures(tmp_path: Path) -> None:
    csv_path = tmp_path / "parse-failures.csv"
    csv_path.write_text(
        "datetime,open,high,low,close,volume\n"
        "not-a-time,1,2,0.5,1.5,10\n"
        "2025-01-01 09:01,1,2,0.5,bad,10\n"
        "2025-01-01 09:02,1,2,0.5,1.5,10\n",
        encoding="utf-8",
    )

    result = inspect_csv(csv_path)

    finding = next(item for item in result.quality_findings if item.code is CsvQualityCode.PARSE_FAILURE)
    assert finding.count == 2
    assert [example.row_number for example in finding.examples] == [2, 3]
    assert result.valid_row_count == 1
    assert result.start_time == datetime(2025, 1, 1, 9, 2)


def test_inspect_csv_reports_empty_data(tmp_path: Path) -> None:
    csv_path = tmp_path / "empty.csv"
    csv_path.write_text("datetime,open,high,low,close,volume\n", encoding="utf-8")

    result = inspect_csv(csv_path)

    assert result.valid_row_count == 0
    assert [item.code for item in result.quality_findings] == [CsvQualityCode.EMPTY_DATA]


def test_inspect_csv_reports_duplicate_and_reversed_timestamps(tmp_path: Path) -> None:
    csv_path = tmp_path / "timestamp-quality.csv"
    csv_path.write_text(
        "datetime,open,high,low,close,volume\n"
        "2025-01-01 09:02,2,3,1,2.5,20\n"
        "2025-01-01 09:01,1,2,0.5,1.5,10\n"
        "2025-01-01 09:02,4,5,3,4.5,30\n",
        encoding="utf-8",
    )

    result = inspect_csv(csv_path)

    by_code = {item.code: item for item in result.quality_findings}
    assert by_code[CsvQualityCode.REVERSED_ORDER].examples[0].row_number == 3
    assert by_code[CsvQualityCode.DUPLICATE_TIMESTAMP].examples[0].row_number == 4
    assert result.valid_row_count == 2
    assert result.duplicates_removed == 1


def test_inspect_csv_reports_ohlc_inconsistency_with_row_example(tmp_path: Path) -> None:
    csv_path = tmp_path / "bad-ohlc.csv"
    csv_path.write_text(
        "datetime,open,high,low,close,volume\n"
        "2025-01-01 09:00,3,2,1,1.5,10\n"
        "2025-01-01 09:01,1,2,0.5,1.5,10\n",
        encoding="utf-8",
    )

    result = inspect_csv(csv_path)

    finding = next(item for item in result.quality_findings if item.code is CsvQualityCode.OHLC_INCONSISTENCY)
    assert finding.count == 1
    assert finding.examples[0].row_number == 2
    assert "open must be between" in finding.examples[0].message
    assert result.valid_row_count == 1


def test_inspect_csv_reports_abnormal_intervals_against_median(tmp_path: Path) -> None:
    csv_path = tmp_path / "gap.csv"
    csv_path.write_text(
        "datetime,open,high,low,close,volume\n"
        "2025-01-01 09:00,1,2,0.5,1.5,10\n"
        "2025-01-01 09:01,1,2,0.5,1.5,10\n"
        "2025-01-01 09:02,1,2,0.5,1.5,10\n"
        "2025-01-01 09:20,1,2,0.5,1.5,10\n",
        encoding="utf-8",
    )

    result = inspect_csv(csv_path)

    finding = next(item for item in result.quality_findings if item.code is CsvQualityCode.ABNORMAL_INTERVAL)
    assert finding.count == 1
    assert finding.examples[0].row_number == 5
    assert "1080" in (finding.examples[0].value or "")


def test_import_custom_headers() -> None:
    temp_dir = Path(".test_tmp") / f"csv-{uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        csv_path = temp_dir / "custom.csv"
        csv_path.write_text(
            "Time,OpenPx,HighPx,LowPx,ClosePx,Vol\n"
            "2025-01-01 09:00,1,2,0.5,1.5,10\n",
            encoding="utf-8",
        )
        result = load_bars_from_csv(
            csv_path,
            field_map={
                "datetime": "Time",
                "open": "OpenPx",
                "high": "HighPx",
                "low": "LowPx",
                "close": "ClosePx",
                "volume": "Vol",
            },
        )
        assert len(result.bars) == 1
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_import_rejects_missing_columns() -> None:
    temp_dir = Path(".test_tmp") / f"csv-{uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        csv_path = temp_dir / "broken.csv"
        csv_path.write_text("datetime,open,high,low,close\n2025-01-01 09:00,1,2,0.5,1.5\n", encoding="utf-8")
        with pytest.raises(MissingColumnsError) as exc_info:
            load_bars_from_csv(csv_path)
        assert exc_info.value.missing_fields == ["volume"]
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_import_accepts_common_aliases_without_manual_mapping() -> None:
    temp_dir = Path(".test_tmp") / f"csv-{uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        csv_path = temp_dir / "aliases.csv"
        csv_path.write_text(
            "time,open,high,low,close,vol\n"
            "2025-01-01 09:00,1,2,0.5,1.5,10\n",
            encoding="utf-8",
        )
        result = load_bars_from_csv(csv_path)
        assert len(result.bars) == 1
        assert result.bars[0].volume == 10
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_import_accepts_chinese_aliases_without_manual_mapping() -> None:
    temp_dir = Path(".test_tmp") / f"csv-{uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        csv_path = temp_dir / "cn.csv"
        csv_path.write_text(
            "日期时间,开盘,最高,最低,收盘,成交量\n"
            "2025-01-01 09:00,1,2,0.5,1.5,10\n",
            encoding="utf-8",
        )
        result = load_bars_from_csv(csv_path)
        assert len(result.bars) == 1
        assert result.bars[0].close == 1.5
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_import_accepts_blank_first_header_when_values_are_datetime() -> None:
    temp_dir = Path(".test_tmp") / f"csv-{uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        csv_path = temp_dir / "blank-header.csv"
        csv_path.write_text(
            ",open,high,low,close,volume\n"
            "2025-01-01 09:00:00,1,2,0.5,1.5,10\n",
            encoding="utf-8",
        )
        result = load_bars_from_csv(csv_path)
        assert len(result.bars) == 1
        assert result.bars[0].timestamp.year == 2025
        assert result.bars[0].open == 1
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_blank_first_header_is_not_misdetected_when_not_datetime() -> None:
    temp_dir = Path(".test_tmp") / f"csv-{uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        csv_path = temp_dir / "blank-header-bad.csv"
        csv_path.write_text(
            ",open,high,low,close,volume\n"
            "not-a-time,1,2,0.5,1.5,10\n",
            encoding="utf-8",
        )
        with pytest.raises(MissingColumnsError) as exc_info:
            load_bars_from_csv(csv_path)
        assert "datetime" in exc_info.value.missing_fields
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_infer_symbol_from_filename_extracts_leading_symbol() -> None:
    parsed = infer_symbol_from_filename("AG9999.XSGE_20250301_20250801_1min.csv")

    assert parsed == "AG9999"


def test_infer_symbol_from_filename_returns_unknown_for_missing_prefix() -> None:
    assert infer_symbol_from_filename("...sample.csv") == "UNKNOWN"


def test_import_reports_empty_numeric_field_with_clear_error() -> None:
    temp_dir = Path(".test_tmp") / f"csv-{uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        csv_path = temp_dir / "empty-close.csv"
        csv_path.write_text(
            "datetime,open,high,low,close,volume\n"
            "2005-01-04 09:16:00,1,2,0.5,,10\n",
            encoding="utf-8",
        )

        with pytest.raises(ValueError) as exc_info:
            load_bars_from_csv(csv_path)

        assert str(exc_info.value) == "Invalid row for timestamp 2005-01-04 09:16:00: numeric field 'close' is empty"
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)




@pytest.mark.parametrize("invalid_value", ["nan", "inf", "-inf"])
def test_import_rejects_non_finite_numeric_values(invalid_value: str) -> None:
    temp_dir = Path(".test_tmp") / f"csv-{uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        csv_path = temp_dir / "non-finite.csv"
        csv_path.write_text(
            "datetime,open,high,low,close,volume\n"
            f"2025-01-01 09:00,1,2,0.5,{invalid_value},10\n",
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="must be finite"):
            load_bars_from_csv(csv_path)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.parametrize(
    ("row", "message"),
    [
        ("1,0.5,2,1.5,10", "high must be greater"),
        ("3,2,1,1.5,10", "open must be between"),
        ("1,2,0.5,3,10", "close must be between"),
        ("1,2,0.5,1.5,-1", "volume must be non-negative"),
    ],
)
def test_import_rejects_invalid_ohlcv_relationships(row: str, message: str) -> None:
    temp_dir = Path(".test_tmp") / f"csv-{uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        csv_path = temp_dir / "invalid-ohlcv.csv"
        csv_path.write_text(
            "datetime,open,high,low,close,volume\n"
            f"2025-01-01 09:00,{row}\n",
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match=message):
            load_bars_from_csv(csv_path)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
