#!/usr/bin/env python3
"""Comprehensive tests for the Metrics module."""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from shadowfs.core.metrics import (
    Metric,
    MetricsCollector,
    MetricType,
    MetricValue,
    get_metrics,
    set_global_metrics,
)


class TestMetricType:
    """Tests for MetricType enum."""

    def test_metric_types(self):
        """Test all metric type values."""
        assert MetricType.COUNTER.value == "counter"
        assert MetricType.GAUGE.value == "gauge"
        assert MetricType.HISTOGRAM.value == "histogram"
        assert MetricType.SUMMARY.value == "summary"

    def test_metric_type_comparison(self):
        """Test metric type comparison."""
        assert MetricType.COUNTER == MetricType.COUNTER
        assert MetricType.COUNTER != MetricType.GAUGE
        assert MetricType.HISTOGRAM != MetricType.SUMMARY


class TestMetricValue:
    """Tests for MetricValue dataclass."""

    def test_metric_value_creation(self):
        """Test creating a metric value."""
        value = MetricValue(value=42.0, labels={"env": "prod"})
        assert value.value == 42.0
        assert value.labels == {"env": "prod"}
        assert isinstance(value.timestamp, float)

    def test_metric_value_defaults(self):
        """Test metric value default values."""
        value = MetricValue(value=10.0)
        assert value.value == 10.0
        assert value.labels == {}
        assert value.timestamp > 0

    def test_metric_value_timestamp(self):
        """Test metric value timestamp can be set manually."""
        # Test that we can provide timestamp
        value = MetricValue(value=5.0, timestamp=1234567890.0)
        assert value.timestamp == 1234567890.0

        # Test that default timestamp is created
        value2 = MetricValue(value=10.0)
        assert isinstance(value2.timestamp, float)
        assert value2.timestamp > 0


class TestMetric:
    """Tests for Metric dataclass."""

    def test_metric_creation(self):
        """Test creating a metric."""
        metric = Metric(
            name="test_metric", metric_type=MetricType.COUNTER, description="Test metric"
        )
        assert metric.name == "test_metric"
        assert metric.metric_type == MetricType.COUNTER
        assert metric.description == "Test metric"
        assert metric.values == []
        assert metric.buckets is None

    def test_histogram_default_buckets(self):
        """Test histogram metric gets default buckets."""
        metric = Metric(
            name="test_histogram", metric_type=MetricType.HISTOGRAM, description="Test histogram"
        )
        assert metric.buckets == [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]

    def test_histogram_custom_buckets(self):
        """Test histogram metric with custom buckets."""
        custom_buckets = [0.1, 0.5, 1.0, 5.0]
        metric = Metric(
            name="test_histogram",
            metric_type=MetricType.HISTOGRAM,
            description="Test histogram",
            buckets=custom_buckets,
        )
        assert metric.buckets == custom_buckets

    def test_non_histogram_buckets(self):
        """Test non-histogram metrics don't get buckets."""
        for metric_type in [MetricType.COUNTER, MetricType.GAUGE, MetricType.SUMMARY]:
            metric = Metric(name="test_metric", metric_type=metric_type, description="Test metric")
            assert metric.buckets is None


class TestMetricsCollector:
    """Tests for MetricsCollector class."""

    def test_collector_creation(self):
        """Test creating a metrics collector."""
        collector = MetricsCollector()
        assert collector.namespace == "shadowfs"
        assert isinstance(collector._metrics, dict)
        assert isinstance(collector._lock, type(threading.RLock()))

    def test_collector_custom_namespace(self):
        """Test collector with custom namespace."""
        collector = MetricsCollector(namespace="custom")
        assert collector.namespace == "custom"

    def test_default_metrics_initialized(self):
        """Test default metrics are initialized."""
        collector = MetricsCollector()

        # Check default counters
        assert "operations_total" in collector._metrics
        assert "errors_total" in collector._metrics

        # Check default histogram
        assert "operation_duration_seconds" in collector._metrics

        # Check default gauges
        assert "cache_size_bytes" in collector._metrics
        assert "open_files" in collector._metrics
        assert "virtual_layers" in collector._metrics

    def test_register_counter(self):
        """Test registering a counter metric."""
        collector = MetricsCollector()
        collector.register_counter("test_counter", "Test counter metric")

        metric = collector._metrics["test_counter"]
        assert metric.name == "test_counter"
        assert metric.metric_type == MetricType.COUNTER
        assert metric.description == "Test counter metric"

    def test_register_counter_duplicate(self):
        """Test registering duplicate counter is ignored."""
        collector = MetricsCollector()
        collector.register_counter("test_counter", "First description")
        collector.register_counter("test_counter", "Second description")

        metric = collector._metrics["test_counter"]
        assert metric.description == "First description"

    def test_register_gauge(self):
        """Test registering a gauge metric."""
        collector = MetricsCollector()
        collector.register_gauge("test_gauge", "Test gauge metric")

        metric = collector._metrics["test_gauge"]
        assert metric.name == "test_gauge"
        assert metric.metric_type == MetricType.GAUGE
        assert metric.description == "Test gauge metric"

    def test_register_histogram(self):
        """Test registering a histogram metric."""
        collector = MetricsCollector()
        collector.register_histogram("test_histogram", "Test histogram metric")

        metric = collector._metrics["test_histogram"]
        assert metric.name == "test_histogram"
        assert metric.metric_type == MetricType.HISTOGRAM
        assert metric.description == "Test histogram metric"
        assert metric.buckets is not None

    def test_register_histogram_custom_buckets(self):
        """Test registering histogram with custom buckets."""
        collector = MetricsCollector()
        buckets = [0.1, 1.0, 10.0]
        collector.register_histogram("test_histogram", "Test", buckets=buckets)

        metric = collector._metrics["test_histogram"]
        assert metric.buckets == buckets

    def test_register_summary(self):
        """Test registering a summary metric."""
        collector = MetricsCollector()
        collector.register_summary("test_summary", "Test summary metric")

        metric = collector._metrics["test_summary"]
        assert metric.name == "test_summary"
        assert metric.metric_type == MetricType.SUMMARY
        assert metric.description == "Test summary metric"

    def test_increment_counter(self):
        """Test incrementing a counter."""
        collector = MetricsCollector()
        collector.register_counter("test_counter", "Test")

        collector.increment_counter("test_counter")
        metric = collector._metrics["test_counter"]
        assert len(metric.values) == 1
        assert metric.values[0].value == 1.0

    def test_increment_counter_with_value(self):
        """Test incrementing counter with specific value."""
        collector = MetricsCollector()
        collector.register_counter("test_counter", "Test")

        collector.increment_counter("test_counter", value=5.0)
        metric = collector._metrics["test_counter"]
        assert metric.values[0].value == 5.0

    def test_increment_counter_with_labels(self):
        """Test incrementing counter with labels."""
        collector = MetricsCollector()
        collector.register_counter("test_counter", "Test")

        collector.increment_counter("test_counter", labels={"env": "prod"})
        metric = collector._metrics["test_counter"]
        assert metric.values[0].labels == {"env": "prod"}

    def test_increment_counter_same_labels(self):
        """Test incrementing counter with same labels adds to existing value."""
        collector = MetricsCollector()
        collector.register_counter("test_counter", "Test")

        collector.increment_counter("test_counter", labels={"env": "prod"}, value=3.0)
        collector.increment_counter("test_counter", labels={"env": "prod"}, value=2.0)

        metric = collector._metrics["test_counter"]
        assert len(metric.values) == 1
        assert metric.values[0].value == 5.0

    def test_increment_counter_different_labels(self):
        """Test incrementing counter with different labels creates new value."""
        collector = MetricsCollector()
        collector.register_counter("test_counter", "Test")

        collector.increment_counter("test_counter", labels={"env": "prod"})
        collector.increment_counter("test_counter", labels={"env": "dev"})

        metric = collector._metrics["test_counter"]
        assert len(metric.values) == 2

    def test_increment_nonexistent_counter(self):
        """Test incrementing non-existent counter is ignored."""
        collector = MetricsCollector()
        collector.increment_counter("nonexistent")  # Should not raise

    def test_increment_wrong_type(self):
        """Test incrementing wrong metric type is ignored."""
        collector = MetricsCollector()
        collector.register_gauge("test_gauge", "Test")
        collector.increment_counter("test_gauge")  # Should not raise

        metric = collector._metrics["test_gauge"]
        assert len(metric.values) == 0

    def test_set_gauge(self):
        """Test setting a gauge value."""
        collector = MetricsCollector()
        collector.register_gauge("test_gauge", "Test")

        collector.set_gauge("test_gauge", 42.0)
        metric = collector._metrics["test_gauge"]
        assert len(metric.values) == 1
        assert metric.values[0].value == 42.0

    def test_set_gauge_with_labels(self):
        """Test setting gauge with labels."""
        collector = MetricsCollector()
        collector.register_gauge("test_gauge", "Test")

        collector.set_gauge("test_gauge", 10.0, labels={"host": "server1"})
        metric = collector._metrics["test_gauge"]
        assert metric.values[0].labels == {"host": "server1"}

    def test_set_gauge_update_existing(self):
        """Test updating existing gauge value with same labels."""
        collector = MetricsCollector()
        collector.register_gauge("test_gauge", "Test")

        collector.set_gauge("test_gauge", 10.0, labels={"host": "server1"})
        collector.set_gauge("test_gauge", 20.0, labels={"host": "server1"})

        metric = collector._metrics["test_gauge"]
        assert len(metric.values) == 1
        assert metric.values[0].value == 20.0

    def test_set_gauge_nonexistent(self):
        """Test setting non-existent gauge is ignored."""
        collector = MetricsCollector()
        collector.set_gauge("nonexistent", 10.0)  # Should not raise

    def test_set_gauge_wrong_type(self):
        """Test setting wrong metric type is ignored."""
        collector = MetricsCollector()
        collector.register_counter("test_counter", "Test")
        collector.set_gauge("test_counter", 10.0)  # Should not raise

        metric = collector._metrics["test_counter"]
        assert len(metric.values) == 0

    def test_record_duration_histogram(self):
        """Test recording duration for histogram."""
        collector = MetricsCollector()
        collector.register_histogram("test_histogram", "Test")

        collector.record_duration("test_histogram", 0.123)
        metric = collector._metrics["test_histogram"]
        assert len(metric.values) == 1
        assert metric.values[0].value == 0.123

    def test_record_duration_summary(self):
        """Test recording duration for summary."""
        collector = MetricsCollector()
        collector.register_summary("test_summary", "Test")

        collector.record_duration("test_summary", 0.456)
        metric = collector._metrics["test_summary"]
        assert len(metric.values) == 1
        assert metric.values[0].value == 0.456

    def test_record_duration_with_labels(self):
        """Test recording duration with labels."""
        collector = MetricsCollector()
        collector.register_histogram("test_histogram", "Test")

        collector.record_duration("test_histogram", 0.1, labels={"op": "read"})
        metric = collector._metrics["test_histogram"]
        assert metric.values[0].labels == {"op": "read"}

    def test_record_duration_nonexistent(self):
        """Test recording duration for non-existent metric is ignored."""
        collector = MetricsCollector()
        collector.record_duration("nonexistent", 0.1)  # Should not raise

    def test_record_duration_wrong_type(self):
        """Test recording duration for wrong metric type is ignored."""
        collector = MetricsCollector()
        collector.register_counter("test_counter", "Test")
        collector.record_duration("test_counter", 0.1)  # Should not raise

        metric = collector._metrics["test_counter"]
        assert len(metric.values) == 0

    def test_get_metric(self):
        """Test getting a metric by name."""
        collector = MetricsCollector()
        collector.register_counter("test_counter", "Test")

        metric = collector.get_metric("test_counter")
        assert metric is not None
        assert metric.name == "test_counter"

    def test_get_metric_nonexistent(self):
        """Test getting non-existent metric returns None."""
        collector = MetricsCollector()
        metric = collector.get_metric("nonexistent")
        assert metric is None

    def test_clear_metrics(self):
        """Test clearing all metric values."""
        collector = MetricsCollector()
        collector.register_counter("test_counter", "Test")
        collector.register_gauge("test_gauge", "Test")

        collector.increment_counter("test_counter")
        collector.set_gauge("test_gauge", 10.0)

        collector.clear_metrics()

        counter = collector._metrics["test_counter"]
        gauge = collector._metrics["test_gauge"]
        assert len(counter.values) == 0
        assert len(gauge.values) == 0

    def test_serialize_labels_empty(self):
        """Test serializing empty labels."""
        collector = MetricsCollector()
        result = collector._serialize_labels({})
        assert result == ""

    def test_serialize_labels_single(self):
        """Test serializing single label."""
        collector = MetricsCollector()
        result = collector._serialize_labels({"key": "value"})
        assert result == "key=value"

    def test_serialize_labels_multiple(self):
        """Test serializing multiple labels (sorted)."""
        collector = MetricsCollector()
        result = collector._serialize_labels({"b": "2", "a": "1", "c": "3"})
        assert result == "a=1,b=2,c=3"

    def test_format_labels_empty(self):
        """Test formatting empty labels for Prometheus."""
        collector = MetricsCollector()
        result = collector._format_labels({})
        assert result == ""

    def test_format_labels_single(self):
        """Test formatting single label for Prometheus."""
        collector = MetricsCollector()
        result = collector._format_labels({"env": "prod"})
        assert result == '{env="prod"}'

    def test_format_labels_multiple(self):
        """Test formatting multiple labels for Prometheus (sorted)."""
        collector = MetricsCollector()
        result = collector._format_labels({"env": "prod", "host": "server1"})
        assert result == '{env="prod",host="server1"}'


class TestPrometheusExport:
    """Tests for Prometheus export functionality."""

    def test_export_empty(self):
        """Test exporting with no metric values."""
        collector = MetricsCollector()
        output = collector.export_prometheus()

        # Should have metric definitions but no values
        assert "# HELP shadowfs_operations_total" in output
        assert "# TYPE shadowfs_operations_total counter" in output

    def test_export_counter(self):
        """Test exporting counter metrics."""
        collector = MetricsCollector()
        collector.register_counter("requests", "Total requests")
        collector.increment_counter("requests", labels={"method": "GET"})

        output = collector.export_prometheus()
        assert "# HELP shadowfs_requests Total requests" in output
        assert "# TYPE shadowfs_requests counter" in output
        assert 'shadowfs_requests{method="GET"} 1' in output

    def test_export_gauge(self):
        """Test exporting gauge metrics."""
        collector = MetricsCollector()
        collector.register_gauge("memory", "Memory usage")
        collector.set_gauge("memory", 1024.0, labels={"type": "heap"})

        output = collector.export_prometheus()
        assert "# HELP shadowfs_memory Memory usage" in output
        assert "# TYPE shadowfs_memory gauge" in output
        assert 'shadowfs_memory{type="heap"} 1024' in output

    def test_export_histogram(self):
        """Test exporting histogram metrics."""
        collector = MetricsCollector()
        collector.register_histogram("latency", "Request latency", buckets=[0.1, 0.5, 1.0])

        # Record some durations
        collector.record_duration("latency", 0.05, labels={"op": "read"})
        collector.record_duration("latency", 0.3, labels={"op": "read"})
        collector.record_duration("latency", 0.7, labels={"op": "read"})
        collector.record_duration("latency", 1.5, labels={"op": "read"})

        output = collector.export_prometheus()

        # Check histogram output
        assert "# HELP shadowfs_latency Request latency" in output
        assert "# TYPE shadowfs_latency histogram" in output

        # Check buckets
        assert 'shadowfs_latency_bucket{le="0.1",op="read"} 1' in output
        assert 'shadowfs_latency_bucket{le="0.5",op="read"} 2' in output
        assert 'shadowfs_latency_bucket{le="1.0",op="read"} 3' in output
        assert 'shadowfs_latency_bucket{le="inf",op="read"} 4' in output

        # Check count and sum
        assert 'shadowfs_latency_count{op="read"} 4' in output
        assert 'shadowfs_latency_sum{op="read"} 2.55' in output

    def test_export_summary(self):
        """Test exporting summary metrics."""
        collector = MetricsCollector()
        collector.register_summary("response_time", "Response time")

        # Record values to calculate quantiles
        for value in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
            collector.record_duration("response_time", value, labels={"service": "api"})

        output = collector.export_prometheus()

        # Check summary output
        assert "# HELP shadowfs_response_time Response time" in output
        assert "# TYPE shadowfs_response_time summary" in output

        # Check quantiles (approximate due to small sample)
        assert 'shadowfs_response_time{quantile="0.5",service="api"}' in output
        assert 'shadowfs_response_time{quantile="0.9",service="api"}' in output
        assert 'shadowfs_response_time{quantile="0.99",service="api"}' in output

        # Check count and sum
        assert 'shadowfs_response_time_count{service="api"} 10' in output
        assert 'shadowfs_response_time_sum{service="api"} 5.5' in output

    def test_aggregate_histogram_empty_labels(self):
        """Test aggregating histogram with empty labels."""
        collector = MetricsCollector()
        metric = Metric(
            name="test", metric_type=MetricType.HISTOGRAM, description="Test", buckets=[0.1, 1.0]
        )
        metric.values = [MetricValue(value=0.05), MetricValue(value=0.5), MetricValue(value=1.5)]

        result = collector._aggregate_histogram(metric)
        assert len(result) == 1
        labels, buckets, count, total_sum = result[0]
        assert labels == {}
        assert count == 3
        assert total_sum == 2.05

    def test_aggregate_histogram_with_labels(self):
        """Test aggregating histogram with different label sets."""
        collector = MetricsCollector()
        metric = Metric(
            name="test", metric_type=MetricType.HISTOGRAM, description="Test", buckets=[0.1, 1.0]
        )
        metric.values = [
            MetricValue(value=0.05, labels={"env": "prod"}),
            MetricValue(value=0.5, labels={"env": "prod"}),
            MetricValue(value=0.2, labels={"env": "dev"}),
        ]

        result = collector._aggregate_histogram(metric)
        assert len(result) == 2

    def test_aggregate_summary_empty_values(self):
        """Test aggregating summary with no values."""
        collector = MetricsCollector()
        metric = Metric(name="test", metric_type=MetricType.SUMMARY, description="Test")

        result = collector._aggregate_summary(metric)
        assert len(result) == 0

    def test_aggregate_summary_single_value(self):
        """Test aggregating summary with single value."""
        collector = MetricsCollector()
        metric = Metric(name="test", metric_type=MetricType.SUMMARY, description="Test")
        metric.values = [MetricValue(value=1.0)]

        result = collector._aggregate_summary(metric)
        assert len(result) == 1
        labels, quantiles, count, total_sum = result[0]
        assert count == 1
        assert total_sum == 1.0


class TestThreadSafety:
    """Tests for thread safety of metrics collector."""

    def test_concurrent_increments(self):
        """Test concurrent counter increments."""
        collector = MetricsCollector()
        collector.register_counter("test_counter", "Test")

        def increment_worker():
            for _ in range(100):
                collector.increment_counter("test_counter")

        threads = []
        for _ in range(10):
            t = threading.Thread(target=increment_worker)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        metric = collector._metrics["test_counter"]
        assert metric.values[0].value == 1000

    def test_concurrent_different_labels(self):
        """Test concurrent operations with different labels."""
        collector = MetricsCollector()
        collector.register_counter("test_counter", "Test")

        def worker(label_value):
            for _ in range(100):
                collector.increment_counter("test_counter", labels={"thread": str(label_value)})

        threads = []
        for i in range(5):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        metric = collector._metrics["test_counter"]
        assert len(metric.values) == 5
        for value in metric.values:
            assert value.value == 100


class TestGlobalMetrics:
    """Tests for global metrics functions."""

    def test_get_metrics_creates_instance(self):
        """Test get_metrics creates new instance."""
        set_global_metrics(None)
        metrics = get_metrics()
        assert metrics is not None
        assert isinstance(metrics, MetricsCollector)

    def test_get_metrics_reuses_instance(self):
        """Test get_metrics reuses existing instance."""
        set_global_metrics(None)
        metrics1 = get_metrics()
        metrics2 = get_metrics()
        assert metrics1 is metrics2

    def test_get_metrics_custom_namespace(self):
        """Test get_metrics with custom namespace."""
        set_global_metrics(None)
        metrics = get_metrics(namespace="custom")
        assert metrics.namespace == "custom"

    def test_set_global_metrics(self):
        """Test setting global metrics instance."""
        custom_metrics = MetricsCollector(namespace="custom")
        set_global_metrics(custom_metrics)

        metrics = get_metrics()
        assert metrics is custom_metrics
        assert metrics.namespace == "custom"
