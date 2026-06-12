from datetime import date


def test_demo_correlation_generates_non_empty_metrics():
    from app.services.analytics_service import get_correlation_metrics

    metrics = get_correlation_metrics(
        start_date=date(2025, 11, 1),
        end_date=date(2025, 11, 3),
        threshold=60,
        proximity_radius=500,
        demo=True,
    )

    assert metrics.data_status == "demo"
    assert metrics.total_intervals > 0
    assert metrics.total_crashes > 0
    assert metrics.true_positives + metrics.false_positives + metrics.true_negatives + metrics.false_negatives == metrics.total_intervals
    assert metrics.precision is not None
    assert metrics.recall is not None
    assert metrics.f1_score is not None
    assert metrics.pearson_correlation is not None
    assert metrics.spearman_correlation is not None
    assert metrics.warnings


def test_demo_validation_rows_feed_charts():
    from app.services.analytics_service import (
        get_scatter_plot_data,
        get_time_series_with_crashes,
        get_weather_impact_analysis,
    )

    start = date(2025, 11, 1)
    end = date(2025, 11, 2)

    scatter = get_scatter_plot_data(start, end, proximity_radius=500, demo=True)
    series = get_time_series_with_crashes(start, end, proximity_radius=500, demo=True)
    weather = get_weather_impact_analysis(start, end, proximity_radius=500, demo=True)

    assert scatter
    assert series
    assert weather
    assert any(row.had_crash for row in scatter)
    assert any(row.had_crash for row in series)
    assert any(row.crash_rate > 0 for row in weather)


def test_demo_flag_is_exposed_through_analytics_api():
    from app.api.analytics import get_correlation, get_scatter_data

    start = date(2025, 11, 1)
    end = date(2025, 11, 1)

    metrics = get_correlation(
        start_date=start,
        end_date=end,
        threshold=60,
        proximity_radius=500,
        demo=True,
    )
    scatter = get_scatter_data(
        start_date=start,
        end_date=end,
        proximity_radius=500,
        demo=True,
    )

    assert metrics.data_status == "demo"
    assert metrics.total_intervals > 0
    assert scatter
