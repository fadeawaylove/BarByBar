from __future__ import annotations

import csv
import math
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from statistics import median

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


class CsvQualityCode(str, Enum):
    MISSING_REQUIRED_FIELDS = "missing_required_fields"
    PARSE_FAILURE = "parse_failure"
    EMPTY_DATA = "empty_data"
    DUPLICATE_TIMESTAMP = "duplicate_timestamp"
    REVERSED_ORDER = "reversed_order"
    OHLC_INCONSISTENCY = "ohlc_inconsistency"
    ABNORMAL_INTERVAL = "abnormal_interval"


class CsvFindingSeverity(str, Enum):
    BLOCKING = "blocking"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class CsvQualityExample:
    row_number: int | None
    message: str
    field: str | None = None
    value: str | None = None


@dataclass(frozen=True, slots=True)
class CsvQualityFinding:
    code: CsvQualityCode
    severity: CsvFindingSeverity
    count: int
    message: str
    examples: tuple[CsvQualityExample, ...]


@dataclass(slots=True)
class CsvInspectionResult:
    source_path: Path
    detected_columns: tuple[str, ...]
    suggested_mapping: dict[str, str]
    sample_rows: tuple[CsvSampleRow, ...]
    valid_row_count: int
    start_time: datetime | None
    end_time: datetime | None
    duplicates_removed: int = 0
    quality_findings: tuple[CsvQualityFinding, ...] = ()

    @property
    def blocking_findings(self) -> tuple[CsvQualityFinding, ...]:
        return tuple(
            finding
            for finding in self.quality_findings
            if finding.severity is CsvFindingSeverity.BLOCKING
        )

    @property
    def warning_findings(self) -> tuple[CsvQualityFinding, ...]:
        return tuple(
            finding
            for finding in self.quality_findings
            if finding.severity is CsvFindingSeverity.WARNING
        )

    @property
    def can_confirm_import(self) -> bool:
        return not self.blocking_findings


@dataclass(slots=True)
class _CsvSource:
    path: Path
    columns: tuple[str, ...]
    rows: list[dict[str, str | None]]
    mapping: dict[str, str]


@dataclass(slots=True)
class _CsvTable:
    path: Path
    columns: tuple[str, ...]
    rows: list[dict[str, str | None]]


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


def _read_csv_table(path: str | Path) -> _CsvTable:
    csv_path = Path(path)
    if not csv_path.exists():
        raise CsvImportError(f"CSV file not found: {csv_path}")
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = tuple(reader.fieldnames or ())
        rows = list(reader) if columns else []
    return _CsvTable(path=csv_path, columns=columns, rows=rows)


def _mapping_for_table(
    table: _CsvTable,
    field_map: dict[str, str] | None,
) -> tuple[dict[str, str], list[str]]:
    sample_row = next(
        (row for row in table.rows if any((value or "").strip() for value in row.values())),
        None,
    )
    mapping = build_field_map(list(table.columns), field_map=field_map, sample_row=sample_row)
    normalized_headers = {normalize_header(name): name for name in table.columns}
    missing = [
        name
        for name in REQUIRED_FIELDS
        if name not in mapping or normalize_header(mapping[name]) not in normalized_headers
    ]
    return mapping, missing


def _read_csv_source(path: str | Path, field_map: dict[str, str] | None = None) -> _CsvSource:
    table = _read_csv_table(path)
    if not table.columns:
        raise CsvImportError("CSV file does not contain headers.")
    mapping, missing = _mapping_for_table(table, field_map)
    if missing:
        raise MissingColumnsError(
            available_headers=list(table.columns),
            missing_fields=missing,
            detected_field_map=mapping,
        )
    return _CsvSource(
        path=table.path,
        columns=table.columns,
        rows=table.rows,
        mapping=mapping,
    )


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
    table = _read_csv_table(path)
    mapping, missing = _mapping_for_table(table, field_map)
    sample_rows: list[CsvSampleRow] = []
    if sample_limit:
        for row_number, row in enumerate(table.rows, start=2):
            values = tuple(row.get(column) or "" for column in table.columns)
            if not any(value.strip() for value in values):
                continue
            sample_rows.append(CsvSampleRow(row_number=row_number, values=values))
            if len(sample_rows) >= sample_limit:
                break

    finding_counts: dict[CsvQualityCode, int] = {}
    finding_examples: dict[CsvQualityCode, list[CsvQualityExample]] = {}

    def record_finding(code: CsvQualityCode, example: CsvQualityExample) -> None:
        finding_counts[code] = finding_counts.get(code, 0) + 1
        examples = finding_examples.setdefault(code, [])
        if len(examples) < 5:
            examples.append(example)

    for field in missing:
        record_finding(
            CsvQualityCode.MISSING_REQUIRED_FIELDS,
            CsvQualityExample(
                row_number=None,
                field=field,
                message=f"Required field '{field}' has no mapped CSV column.",
            ),
        )

    bars: list[Bar] = []
    duplicates_removed = 0
    parseable_timestamps: list[tuple[int, datetime]] = []
    seen_timestamps: set[datetime] = set()
    previous_timestamp: datetime | None = None
    if not missing:
        normalized_headers = {normalize_header(name): name for name in table.columns}
        resolved = {
            field: normalized_headers[normalize_header(mapping[field])]
            for field in REQUIRED_FIELDS
        }
        for row_number, row in enumerate(table.rows, start=2):
            raw_timestamp = row[resolved["datetime"]] or ""
            try:
                timestamp = parse_datetime(raw_timestamp)
            except CsvImportError as exc:
                record_finding(
                    CsvQualityCode.PARSE_FAILURE,
                    CsvQualityExample(
                        row_number=row_number,
                        field="datetime",
                        value=raw_timestamp,
                        message=str(exc),
                    ),
                )
                continue
            parseable_timestamps.append((row_number, timestamp))
            if previous_timestamp is not None and timestamp < previous_timestamp:
                record_finding(
                    CsvQualityCode.REVERSED_ORDER,
                    CsvQualityExample(
                        row_number=row_number,
                        field="datetime",
                        value=raw_timestamp,
                        message="Timestamp is earlier than the preceding parseable row.",
                    ),
                )
            previous_timestamp = timestamp
            if timestamp in seen_timestamps:
                duplicates_removed += 1
                record_finding(
                    CsvQualityCode.DUPLICATE_TIMESTAMP,
                    CsvQualityExample(
                        row_number=row_number,
                        field="datetime",
                        value=raw_timestamp,
                        message="Timestamp duplicates an earlier importable row.",
                    ),
                )
                continue
            try:
                bar = Bar(
                    timestamp=timestamp,
                    open=_parse_numeric_field(row[resolved["open"]], "open", timestamp),
                    high=_parse_numeric_field(row[resolved["high"]], "high", timestamp),
                    low=_parse_numeric_field(row[resolved["low"]], "low", timestamp),
                    close=_parse_numeric_field(row[resolved["close"]], "close", timestamp),
                    volume=_parse_numeric_field(row[resolved["volume"]], "volume", timestamp),
                )
            except CsvImportError as exc:
                record_finding(
                    CsvQualityCode.PARSE_FAILURE,
                    CsvQualityExample(
                        row_number=row_number,
                        message=str(exc),
                    ),
                )
                continue
            try:
                _validate_bar(bar)
            except CsvImportError as exc:
                record_finding(
                    CsvQualityCode.OHLC_INCONSISTENCY,
                    CsvQualityExample(
                        row_number=row_number,
                        message=str(exc),
                    ),
                )
                continue
            seen_timestamps.add(timestamp)
            bars.append(bar)

    positive_intervals = [
        (current_row, (current_time - previous_time).total_seconds())
        for (_, previous_time), (current_row, current_time) in zip(
            parseable_timestamps,
            parseable_timestamps[1:],
        )
        if current_time > previous_time
    ]
    if len(positive_intervals) >= 3:
        baseline_seconds = median(seconds for _, seconds in positive_intervals)
        if baseline_seconds > 0:
            for row_number, interval_seconds in positive_intervals:
                if interval_seconds <= baseline_seconds * 3:
                    continue
                record_finding(
                    CsvQualityCode.ABNORMAL_INTERVAL,
                    CsvQualityExample(
                        row_number=row_number,
                        field="datetime",
                        value=f"{interval_seconds:g} seconds",
                        message=f"Interval exceeds three times the median ({baseline_seconds:g} seconds).",
                    ),
                )

    if not bars:
        record_finding(
            CsvQualityCode.EMPTY_DATA,
            CsvQualityExample(
                row_number=None,
                message="CSV file does not contain any importable rows.",
            ),
        )
    bars.sort(key=lambda item: item.timestamp)
    finding_messages = {
        CsvQualityCode.MISSING_REQUIRED_FIELDS: "Required fields are not mapped.",
        CsvQualityCode.PARSE_FAILURE: "Some rows contain values that cannot be parsed.",
        CsvQualityCode.EMPTY_DATA: "No importable rows were found.",
        CsvQualityCode.DUPLICATE_TIMESTAMP: "Duplicate timestamps were found.",
        CsvQualityCode.REVERSED_ORDER: "Timestamps are not in ascending source order.",
        CsvQualityCode.OHLC_INCONSISTENCY: "Some rows contain inconsistent OHLCV values.",
        CsvQualityCode.ABNORMAL_INTERVAL: "Some timestamp intervals are unusually large.",
    }
    finding_severities = {
        CsvQualityCode.MISSING_REQUIRED_FIELDS: CsvFindingSeverity.BLOCKING,
        CsvQualityCode.PARSE_FAILURE: CsvFindingSeverity.BLOCKING,
        CsvQualityCode.EMPTY_DATA: CsvFindingSeverity.BLOCKING,
        CsvQualityCode.DUPLICATE_TIMESTAMP: CsvFindingSeverity.WARNING,
        CsvQualityCode.REVERSED_ORDER: CsvFindingSeverity.WARNING,
        CsvQualityCode.OHLC_INCONSISTENCY: CsvFindingSeverity.BLOCKING,
        CsvQualityCode.ABNORMAL_INTERVAL: CsvFindingSeverity.WARNING,
    }
    finding_order = tuple(CsvQualityCode)
    quality_findings = tuple(
        CsvQualityFinding(
            code=code,
            severity=finding_severities[code],
            count=finding_counts[code],
            message=finding_messages[code],
            examples=tuple(finding_examples[code]),
        )
        for code in finding_order
        if code in finding_counts
    )
    return CsvInspectionResult(
        source_path=table.path,
        detected_columns=table.columns,
        suggested_mapping=dict(mapping),
        sample_rows=tuple(sample_rows),
        valid_row_count=len(bars),
        start_time=bars[0].timestamp if bars else None,
        end_time=bars[-1].timestamp if bars else None,
        duplicates_removed=duplicates_removed,
        quality_findings=quality_findings,
    )


def load_bars_from_csv(path: str | Path, field_map: dict[str, str] | None = None) -> ImportResult:
    return _parse_bars(_read_csv_source(path, field_map=field_map))
