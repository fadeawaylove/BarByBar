from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from barbybar.domain.models import Bar


DEFAULT_FIELD_MAP = {
    "datetime": "datetime",
    "open": "open",
    "high": "high",
    "low": "low",
    "close": "close",
    "volume": "volume",
}


@dataclass(slots=True)
class ImportResult:
    bars: list[Bar]
    duplicates_removed: int = 0


class CsvImportError(ValueError):
    pass


def normalize_header(header: str) -> str:
    return header.strip().lower().replace(" ", "").replace("_", "")


def parse_datetime(value: str) -> datetime:
    candidates = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y-%m-%d",
    ]
    for fmt in candidates:
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    raise CsvImportError(f"Unsupported datetime format: {value}")


def load_bars_from_csv(path: str | Path, field_map: dict[str, str] | None = None) -> ImportResult:
    csv_path = Path(path)
    if not csv_path.exists():
        raise CsvImportError(f"CSV file not found: {csv_path}")
    mapping = {key: normalize_header(value) for key, value in (field_map or DEFAULT_FIELD_MAP).items()}
    bars: list[Bar] = []
    duplicates_removed = 0
    seen_timestamps: set[datetime] = set()
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise CsvImportError("CSV file does not contain headers.")
        normalized_headers = {normalize_header(name): name for name in reader.fieldnames}
        required = ["datetime", "open", "high", "low", "close", "volume"]
        missing = [name for name in required if mapping[name] not in normalized_headers]
        if missing:
            raise CsvImportError(f"Missing required columns: {', '.join(missing)}")

        for row in reader:
            timestamp = parse_datetime(row[normalized_headers[mapping["datetime"]]])
            if timestamp in seen_timestamps:
                duplicates_removed += 1
                continue
            try:
                bar = Bar(
                    timestamp=timestamp,
                    open=float(row[normalized_headers[mapping["open"]]]),
                    high=float(row[normalized_headers[mapping["high"]]]),
                    low=float(row[normalized_headers[mapping["low"]]]),
                    close=float(row[normalized_headers[mapping["close"]]]),
                    volume=float(row[normalized_headers[mapping["volume"]]]),
                )
            except (TypeError, ValueError) as exc:
                raise CsvImportError(f"Invalid row for timestamp {timestamp}: {exc}") from exc
            seen_timestamps.add(timestamp)
            bars.append(bar)
    if not bars:
        raise CsvImportError("CSV file does not contain usable rows.")
    bars.sort(key=lambda item: item.timestamp)
    return ImportResult(bars=bars, duplicates_removed=duplicates_removed)
