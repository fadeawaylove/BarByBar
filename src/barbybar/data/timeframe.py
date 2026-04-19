from __future__ import annotations

from bisect import bisect_right
from datetime import date, datetime, time, timedelta

from barbybar.domain.models import Bar

MINUTE_TIMEFRAMES = ("1m", "2m", "5m", "15m", "30m", "60m")
SUPPORTED_REPLAY_TIMEFRAMES = ("5m", "15m", "30m", "60m", "1d")
DAY_TIMEFRAME = "1d"
DAY_SESSION_OPEN = time(9, 0)
NIGHT_SESSION_OPEN = time(21, 0)


def normalize_timeframe(value: str) -> str:
    timeframe = value.strip().lower()
    aliases = {
        "1": "1m",
        "2": "2m",
        "5": "5m",
        "15": "15m",
        "30": "30m",
        "60": "60m",
        "1min": "1m",
        "2min": "2m",
        "5min": "5m",
        "15min": "15m",
        "30min": "30m",
        "60min": "60m",
        "d": "1d",
        "day": "1d",
        "daily": "1d",
    }
    return aliases.get(timeframe, timeframe)


def timeframe_to_minutes(timeframe: str) -> int:
    normalized = normalize_timeframe(timeframe)
    if normalized == DAY_TIMEFRAME:
        return 60 * 24
    if normalized.endswith("m") and normalized[:-1].isdigit():
        return int(normalized[:-1])
    raise ValueError(f"Unsupported timeframe: {timeframe}")


def default_chart_timeframe(source_timeframe: str) -> str:
    normalized = normalize_timeframe(source_timeframe)
    supported = supported_replay_timeframes(normalized)
    if normalized in supported:
        return normalized
    if supported:
        return supported[0]
    return normalized


def supported_replay_timeframes(source_timeframe: str) -> list[str]:
    source = normalize_timeframe(source_timeframe)
    if source == DAY_TIMEFRAME:
        return [DAY_TIMEFRAME]
    source_minutes = timeframe_to_minutes(source)
    result: list[str] = []
    for candidate in SUPPORTED_REPLAY_TIMEFRAMES:
        if candidate == DAY_TIMEFRAME:
            result.append(candidate)
            continue
        candidate_minutes = timeframe_to_minutes(candidate)
        if candidate_minutes >= source_minutes and candidate_minutes % source_minutes == 0:
            result.append(candidate)
    return result


def aggregate_bars(bars: list[Bar], source_timeframe: str, target_timeframe: str) -> list[Bar]:
    source = normalize_timeframe(source_timeframe)
    target = normalize_timeframe(target_timeframe)
    if source == target:
        return list(bars)
    if target == DAY_TIMEFRAME:
        return _aggregate_daily_bars(bars)
    source_minutes = timeframe_to_minutes(source)
    target_minutes = timeframe_to_minutes(target)
    if target_minutes < source_minutes or target_minutes % source_minutes != 0:
        raise ValueError(f"Cannot aggregate {source_timeframe} into {target_timeframe}.")
    factor = target_minutes // source_minutes
    if not bars:
        return []
    aggregated: list[Bar] = []
    expected_step = timedelta(minutes=source_minutes)
    bucket: list[Bar] = []
    for bar in sorted(bars, key=lambda item: item.timestamp):
        if bucket and bar.timestamp - bucket[-1].timestamp != expected_step:
            if len(bucket) == factor:
                aggregated.append(_aggregate_bucket(bucket))
            bucket = []
        bucket.append(bar)
        if len(bucket) == factor:
            aggregated.append(_aggregate_bucket(bucket))
            bucket = []
    return aggregated


def find_bar_index_for_timestamp(bars: list[Bar], timestamp: datetime | None) -> int:
    if not bars:
        return 0
    if timestamp is None:
        return 0
    timestamps = [bar.timestamp for bar in bars]
    return max(0, min(bisect_right(timestamps, timestamp) - 1, len(bars) - 1))


def find_timestamp_index(timestamps: list[datetime], timestamp: datetime | None) -> int:
    if not timestamps:
        return 0
    if timestamp is None:
        return 0
    return max(0, min(bisect_right(timestamps, timestamp) - 1, len(timestamps) - 1))


def find_timestamp_window(
    timestamps: list[datetime],
    anchor_time: datetime | None,
    before_count: int,
    after_count: int,
) -> tuple[int, int, int]:
    if not timestamps:
        return 0, -1, 0
    anchor_index = find_timestamp_index(timestamps, anchor_time)
    start = max(0, anchor_index - max(before_count, 0))
    end = min(len(timestamps) - 1, anchor_index + max(after_count, 0))
    return start, end, anchor_index


def _aggregate_bucket(bucket: list[Bar]) -> Bar:
    return Bar(
        timestamp=bucket[-1].timestamp,
        open=bucket[0].open,
        high=max(item.high for item in bucket),
        low=min(item.low for item in bucket),
        close=bucket[-1].close,
        volume=sum(item.volume for item in bucket),
        open_timestamp=bucket[0].open_timestamp,
    )


def _aggregate_daily_bars(bars: list[Bar]) -> list[Bar]:
    if not bars:
        return []
    ordered = sorted(bars, key=lambda item: item.timestamp)
    has_night_session = _has_night_session(ordered)
    aggregated: list[Bar] = []
    bucket: list[Bar] = []
    current_key: date | None = None
    for bar in ordered:
        bucket_key = _daily_bucket_key(bar.timestamp, has_night_session)
        if current_key is None or bucket_key == current_key:
            bucket.append(bar)
            current_key = bucket_key
            continue
        aggregated.append(_aggregate_bucket(bucket))
        bucket = [bar]
        current_key = bucket_key
    if bucket:
        aggregated.append(_aggregate_bucket(bucket))
    return aggregated


def _has_night_session(bars: list[Bar]) -> bool:
    return any(bar.timestamp.time() >= NIGHT_SESSION_OPEN or bar.timestamp.time() < DAY_SESSION_OPEN for bar in bars)


def _daily_bucket_key(timestamp: datetime, has_night_session: bool) -> date:
    if not has_night_session:
        return timestamp.date()
    bar_time = timestamp.time()
    if bar_time >= NIGHT_SESSION_OPEN:
        return (timestamp + timedelta(days=1)).date()
    return timestamp.date()
