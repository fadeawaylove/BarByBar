from pathlib import Path

import pytest

from barbybar.data.csv_importer import CsvImportError, load_bars_from_csv


def test_import_standard_csv() -> None:
    result = load_bars_from_csv(Path("sample_data/if_sample.csv"))
    assert len(result.bars) == 10
    assert result.bars[0].open == 3860.0
    assert result.bars[-1].close == 3884.0


def test_import_custom_headers(tmp_path: Path) -> None:
    csv_path = tmp_path / "custom.csv"
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


def test_import_rejects_missing_columns(tmp_path: Path) -> None:
    csv_path = tmp_path / "broken.csv"
    csv_path.write_text("datetime,open,high,low,close\n2025-01-01 09:00,1,2,0.5,1.5\n", encoding="utf-8")
    with pytest.raises(CsvImportError):
        load_bars_from_csv(csv_path)
