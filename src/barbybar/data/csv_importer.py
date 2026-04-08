from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from barbybar.domain.models import Bar

REQUIRED_FIELDS = ["datetime", "open", "high", "low", "close", "volume"]

DEFAULT_FIELD_MAP = {
    "datetime": "datetime",
    "open": "open",
    "high": "high",
    "low": "low",
    "close": "close",
    "volume": "volume",
}

FIELD_ALIASES = {
    "datetime": ["datetime", "date", "time", "timestamp", "tradingtime", "日期", "时间", "日期时间"],
    "open": ["open", "o", "开盘", "开盘价"],
    "high": ["high", "h", "最高", "最高价"],
    "low": ["low", "l", "最低", "最低价"],
    "close": ["close", "c", "收盘", "收盘价", "last"],
    "volume": ["volume", "vol", "成交量", "手数"],
}


@dataclass(slots=True)
class ImportResult:
    bars: list[Bar]
    duplicates_removed: int = 0


class CsvImportError(ValueError):
    pass


class MissingColumnsError(CsvImportError):
    def __init__(self, available_headers: list[str], missing_fields: list[str], detected_field_map: dict[str, str]) -> None:
        self.available_headers = available_headers
        self.missing_fields = missing_fields
        self.detected_field_map = detected_field_map
        super().__init__(f"Missing required columns: {', '.join(missing_fields)}")


SYMBOL_PREFIX_PATTERN = re.compile(r"^(?P<symbol>[A-Za-z0-9]+)")


def normalize_header(header: str) -> str:
    return header.strip().lower().replace(" ", "").replace("_", "")


def infer_symbol_from_filename(path: str | Path) -> str:
    stem = Path(path).stem.strip()
    matched = SYMBOL_PREFIX_PATTERN.match(stem)
    if matched is None:
        return "UNKNOWN"
    symbol = matched.group("symbol").strip().upper()
    return symbol or "UNKNOWN"


def _looks_like_datetime(value: str | None) -> bool:
    if value is None or not value.strip():
        return False
    try:
        parse_datetime(value)
    except CsvImportError:
        return False
    return True


def build_field_map(
    fieldnames: list[str],
    field_map: dict[str, str] | None = None,
    sample_row: dict[str, str] | None = None,
) -> dict[str, str]:
    normalized_headers = {normalize_header(name): name for name in fieldnames}
    detected: dict[str, str] = {}
    blank_header = normalized_headers.get("")
    if blank_header is not None and sample_row and _looks_like_datetime(sample_row.get(blank_header)):
        detected["datetime"] = blank_header
    for required_field in REQUIRED_FIELDS:
        if required_field in detected:
            continue
        aliases = [normalize_header(alias) for alias in FIELD_ALIASES.get(required_field, [required_field])]
        aliases.extend([normalize_header(DEFAULT_FIELD_MAP[required_field])])
        for alias in aliases:
            original = normalized_headers.get(alias)
            if original is not None:
                detected[required_field] = original
                break
    for key, value in (field_map or {}).items():
        if key in REQUIRED_FIELDS:
            detected[key] = value
    return detected


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
    bars: list[Bar] = []
    duplicates_removed = 0
    seen_timestamps: set[datetime] = set()
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise CsvImportError("CSV file does not contain headers.")
        preview_rows = list(reader)
        sample_row = next((row for row in preview_rows if any((value or "").strip() for value in row.values())), None)
        mapping = build_field_map(reader.fieldnames, field_map=field_map, sample_row=sample_row)
        normalized_headers = {normalize_header(name): name for name in reader.fieldnames}
        missing = [name for name in REQUIRED_FIELDS if name not in mapping or normalize_header(mapping[name]) not in normalized_headers]
        if missing:
            raise MissingColumnsError(
                available_headers=list(reader.fieldnames),
                missing_fields=missing,
                detected_field_map=mapping,
            )

        for row in preview_rows:
            timestamp = parse_datetime(row[normalized_headers[normalize_header(mapping["datetime"])]] )
            if timestamp in seen_timestamps:
                duplicates_removed += 1
                continue
            try:
                bar = Bar(
                    timestamp=timestamp,
                    open=float(row[normalized_headers[normalize_header(mapping["open"])]]),
                    high=float(row[normalized_headers[normalize_header(mapping["high"])]]),
                    low=float(row[normalized_headers[normalize_header(mapping["low"])]]),
                    close=float(row[normalized_headers[normalize_header(mapping["close"])]]),
                    volume=float(row[normalized_headers[normalize_header(mapping["volume"])]]),
                )
            except (TypeError, ValueError) as exc:
                raise CsvImportError(f"Invalid row for timestamp {timestamp}: {exc}") from exc
            seen_timestamps.add(timestamp)
            bars.append(bar)
    if not bars:
        raise CsvImportError("CSV file does not contain usable rows.")
    bars.sort(key=lambda item: item.timestamp)
    return ImportResult(bars=bars, duplicates_removed=duplicates_removed)
