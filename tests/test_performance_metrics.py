from barbybar.performance_metrics import PerformanceMetricsStore, clear_metrics, performance_summary_lines, recent_metrics, record_metric


def test_performance_metrics_store_keeps_recent_bounded_metrics() -> None:
    store = PerformanceMetricsStore(maxlen=3)

    for index in range(5):
        store.record("chart", "viewport_apply", index, index=index)

    recent = store.recent(10)

    assert len(recent) == 3
    assert [metric.context_dict()["index"] for metric in recent] == [4, 3, 2]


def test_global_performance_summary_includes_context() -> None:
    clear_metrics()

    record_metric("chart", "overlay_refresh", 1.234, bars=120, interactive=True)

    lines = performance_summary_lines(1)

    assert len(recent_metrics()) == 1
    assert "chart.overlay_refresh" in lines[0]
    assert "interactive=True" in lines[0]
    assert "bars=120" in lines[0]
