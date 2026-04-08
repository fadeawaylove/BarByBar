from pathlib import Path
import shutil
from uuid import uuid4

import pytest

from barbybar.data.csv_importer import CsvImportError, MissingColumnsError, load_bars_from_csv, parse_import_filename


def test_import_standard_csv() -> None:
    result = load_bars_from_csv(Path("sample_data/if_sample.csv"))
    assert len(result.bars) == 10
    assert result.bars[0].open == 3860.0
    assert result.bars[-1].close == 3884.0


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


def test_parse_import_filename_extracts_symbol_and_timeframe() -> None:
    parsed = parse_import_filename("AG9999.XSGE_20250301_20250801_1min.csv")

    assert parsed.symbol == "AG9999"
    assert parsed.exchange == "XSGE"
    assert parsed.start_date == "20250301"
    assert parsed.end_date == "20250801"
    assert parsed.timeframe == "1m"


def test_parse_import_filename_rejects_unexpected_pattern() -> None:
    with pytest.raises(CsvImportError):
        parse_import_filename("sample.csv")
