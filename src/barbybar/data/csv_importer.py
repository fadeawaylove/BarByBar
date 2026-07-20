from __future__ import annotations

import csv
import math
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


@dataclass(frozen=True, slots=True)
class CsvSampleRow:
    row_number: int
    values: tuple[str, ...]


@dataclass(slots=True)
class CsvInspectionResult:
    source_path: Path
    detected_columns: tuple[str, ...]
    suggested_mapping: dict[str, str]
    sample_rows: tuple[CsvSampleRow, ...]
    valid_row_count: int
    start_time: datetime
    end_time: datetime
    duplicates_removed: int = 0


@dataclass(slots=True)
class _CsvSource:
    path: Path
    columns: tuple[str, ...]
    rows: list[dict[str, str | None]]
    mapping: dict[str, str]


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


def _parse_numeric_field(raw_value: str | None, field_name: str, timestamp: datetime) -> float:
    value = (raw_value or "").strip()
    if not value:
        raise CsvImportError(f"Invalid row for timestamp {timestamp}: numeric field '{field_name}' is empty")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise CsvImportError(f"Invalid row for timestamp {timestamp}: field '{field_name}' is not a valid number") from exc
    if not math.isfinite(parsed):
        raise CsvImportError(f"Invalid row for timestamp {timestamp}: field '{field_name}' must be finite")
    return parsed


def _validate_bar(bar: Bar) -> None:
    timestamp = bar.timestamp
    if bar.high < bar.low:
        raise CsvImportError(f"Invalid row for timestamp {timestamp}: high must be greater than or equal to low")
    if not bar.low <= bar.open <= bar.high:
        raise CsvImportError(f"Invalid row for timestamp {timestamp}: open must be between low and high")
    if not bar.low <= bar.close <= bar.high:
        raise CsvImportError(f"Invalid row for timestamp {timestamp}: close must be between low and high")
    if bar.volume < 0:
        raise CsvImportError(f"Invalid row for timestamp {timestamp}: volume must be non-negative")


def _read_csv_source(path: str | Path, field_map: dict[str, str] | None = None) -> _CsvSource:
    csv_path = Path(path)
    if not csv_path.exists():
        raise CsvImportError(f"CSV file not found: {csv_path}")
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise CsvImportError("CSV file does not contain headers.")
        columns = tuple(reader.fieldnames)
        rows = list(reader)
    sample_row = next(
        (row for row in rows if any((value or "").strip() for value in row.values())),
        None,
    )
    mapping = build_field_map(list(columns), field_map=field_map, sample_row=sample_row)
    normalized_headers = {normalize_header(name): name for name in columns}
    missing = [
        name
        for name in REQUIRED_FIELDS
        if name not in mapping or normalize_header(mapping[name]) not in normalized_headers
    ]
    if missing:
        raise MissingColumnsError(
            available_headers=list(columns),
            missing_fields=missing,
            detected_field_map=mapping,
        )
    return _CsvSource(path=csv_path, columns=columns, rows=rows, mapping=mapping)


def _parse_bars(source: _CsvSource) -> ImportResult:
    bars: list[Bar] = []
    duplicates_removed = 0
    seen_timestamps: set[datetime] = set()
    normalized_headers = {normalize_header(name): name for name in source.columns}
    resolved = {
        field: normalized_headers[normalize_header(source.mapping[field])]
        for field in REQUIRED_FIELDS
    }
    for row in source.rows:
        timestamp = parse_datetime(row[resolved["datetime"]] or "")
        if timestamp in seen_timestamps:
            duplicates_removed += 1
            continue
        bar = Bar(
            timestamp=timestamp,
            open=_parse_numeric_field(row[resolved["open"]], "open", timestamp),
            high=_parse_numeric_field(row[resolved["high"]], "high", timestamp),
            low=_parse_numeric_field(row[resolved["low"]], "low", timestamp),
            close=_parse_numeric_field(row[resolved["close"]], "close", timestamp),
            volume=_parse_numeric_field(row[resolved["volume"]], "volume", timestamp),
        )
        _validate_bar(bar)
        seen_timestamps.add(timestamp)
        bars.append(bar)
    if not bars:
        raise CsvImportError("CSV file does not contain usable rows.")
    bars.sort(key=lambda item: item.timestamp)
    return ImportResult(bars=bars, duplicates_removed=duplicates_removed)


def inspect_csv(
    path: str | Path,
    field_map: dict[str, str] | None = None,
    *,
    sample_limit: int = 5,
) -> CsvInspectionResult:
    if sample_limit < 0:
        raise ValueError("sample_limit must be greater than or equal to zero")
    source = _read_csv_source(path, field_map=field_map)
    parsed = _parse_bars(source)
    sample_rows: list[CsvSampleRow] = []
    if sample_limit:
        for row_number, row in enumerate(source.rows, start=2):
            values = tuple(row.get(column) or "" for column in source.columns)
            if not any(value.strip() for value in values):
                continue
            sample_rows.append(CsvSampleRow(row_number=row_number, values=values))
            if len(sample_rows) >= sample_limit:
                break
    bars = parsed.bars
    return CsvInspectionResult(
        source_path=source.path,
        detected_columns=source.columns,
        suggested_mapping=dict(source.mapping),
        sample_rows=tuple(sample_rows),
        valid_row_count=len(bars),
        start_time=bars[0].timestamp,
        end_time=bars[-1].timestamp,
        duplicates_removed=parsed.duplicates_removed,
    )


def load_bars_from_csv(path: str | Path, field_map: dict[str, str] | None = None) -> ImportResult:
    return _parse_bars(_read_csv_source(path, field_map=field_map))
