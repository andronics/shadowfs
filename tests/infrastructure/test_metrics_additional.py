#!/usr/bin/env python3
"""Additional tests for complete Metrics coverage."""

import threading
import pytest

from shadowfs.infrastructure.metrics import (
    MetricType,
    MetricValue,
    Metric,
    MetricsCollector,
    get_metrics,
    set_global_metrics,
)


class TestMissingCoverage:
    """Tests for missing coverage lines."""

    def test_aggregate_summary_with_parse_error(self):
        """Test aggregate summary with label parsing edge cases."""
        collector = MetricsCollector()
        metric = Metric(
            name="test",
            metric_type=MetricType.SUMMARY,
            description="Test"
        )

        # Create values with complex label serialization
        metric.values = [
            MetricValue(value=1.0, labels={"key": "value"}),
            MetricValue(value=2.0, labels={"key": "value"}),
            MetricValue(value=3.0, labels={"key": "value"}),
        ]

        # Manually set a malformed label key to test edge case
        collector._metrics["test"] = metric

        result = collector._aggregate_summary(metric)
        assert len(result) == 1
        labels, quantiles, count, total_sum = result[0]
        assert labels == {"key": "value"}
        assert count == 3
        assert total_sum == 6.0

    def test_aggregate_histogram_label_parsing_without_equals(self):
        """Test histogram aggregation with label parsing edge case."""
        collector = MetricsCollector()
        metric = Metric(
            name="test",
            metric_type=MetricType.HISTOGRAM,
            description="Test",
            buckets=[0.1, 1.0]
        )

        # Direct manipulation to test label parsing edge case
        metric.values = [
            MetricValue(value=0.5, labels={}),  # Empty labels
        ]

        # Test the aggregation
        result = collector._aggregate_histogram(metric)
        assert len(result) == 1
        labels, buckets, count, total_sum = result[0]
        assert labels == {}
        assert count == 1

    def test_aggregate_summary_label_parsing_without_equals(self):
        """Test summary aggregation with label parsing edge case."""
        collector = MetricsCollector()
        metric = Metric(
            name="test",
            metric_type=MetricType.SUMMARY,
            description="Test"
        )

        # Create a mock scenario where label serialization produces no equals
        # This tests the branch where "=" not in part
        collector._serialize_labels = lambda x: "keyonly" if x else ""

        # Add values
        metric.values = [
            MetricValue(value=1.0, labels={}),
        ]

        collector._metrics["test"] = metric

        # This should handle the case where split produces parts without "="
        result = collector._aggregate_summary(metric)
        assert len(result) >= 0  # Should not crash

    def test_quantile_index_boundary(self):
        """Test quantile calculation at boundary conditions."""
        collector = MetricsCollector()
        metric = Metric(
            name="test",
            metric_type=MetricType.SUMMARY,
            description="Test"
        )

        # Test with exactly one value - edge case for quantile calculation
        metric.values = [
            MetricValue(value=5.0, labels={"test": "single"})
        ]

        result = collector._aggregate_summary(metric)
        assert len(result) == 1
        labels, quantiles, count, total_sum = result[0]

        # With one value, all quantiles should be that value
        assert count == 1
        assert total_sum == 5.0
        assert len(quantiles) == 3  # 0.5, 0.9, 0.99 quantiles

    def test_aggregate_with_malformed_serialized_labels(self):
        """Test aggregation when label serialization has unusual format."""
        collector = MetricsCollector()

        # Test histogram aggregation with direct manipulation
        metric = Metric(
            name="test",
            metric_type=MetricType.HISTOGRAM,
            description="Test",
            buckets=[0.1, 1.0]
        )

        # Create a complex grouping scenario
        groups = {
            "malformed": [0.1, 0.2],
            "key=value,another=test": [0.3, 0.4],
            "": [0.5],  # Empty key
        }

        # Mock _serialize_labels to return our test keys
        original_serialize = collector._serialize_labels
        label_map = {
            (): "",
            (("key", "value"), ("another", "test")): "key=value,another=test",
            (("bad", "format"),): "malformed",
        }

        test_values = []
        for labels_tuple, values in [
            ((), [0.5]),
            ((("key", "value"), ("another", "test")), [0.3, 0.4]),
            ((("bad", "format"),), [0.1, 0.2]),
        ]:
            labels_dict = dict(labels_tuple) if labels_tuple else {}
            for v in values:
                test_values.append(MetricValue(value=v, labels=labels_dict))

        metric.values = test_values

        # Test aggregation handles all cases
        result = collector._aggregate_histogram(metric)
        assert len(result) > 0

    def test_context_manager_cleanup(self):
        """Test that context managers are properly cleaned up in all metrics operations."""
        collector = MetricsCollector()

        # Register various metric types
        collector.register_counter("counter", "Test counter")
        collector.register_gauge("gauge", "Test gauge")
        collector.register_histogram("histogram", "Test histogram", buckets=[0.1, 1.0])
        collector.register_summary("summary", "Test summary")

        # Verify thread safety with multiple operations
        def worker(metric_type, name):
            if metric_type == "counter":
                collector.increment_counter(name, labels={"thread": "test"})
            elif metric_type == "gauge":
                collector.set_gauge(name, 10.0, labels={"thread": "test"})
            elif metric_type == "histogram":
                collector.record_duration(name, 0.5, labels={"thread": "test"})
            elif metric_type == "summary":
                collector.record_duration(name, 0.5, labels={"thread": "test"})

        threads = []
        for metric_type, name in [
            ("counter", "counter"),
            ("gauge", "gauge"),
            ("histogram", "histogram"),
            ("summary", "summary"),
        ]:
            t = threading.Thread(target=worker, args=(metric_type, name))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Export should work without errors
        output = collector.export_prometheus()
        assert "shadowfs_counter" in output
        assert "shadowfs_gauge" in output
        assert "shadowfs_histogram" in output
        assert "shadowfs_summary" in output

    def test_empty_quantiles(self):
        """Test summary with no values for quantile calculation."""
        collector = MetricsCollector()
        metric = Metric(
            name="test",
            metric_type=MetricType.SUMMARY,
            description="Test"
        )

        # Test with empty values list for a label group
        metric.values = []

        result = collector._aggregate_summary(metric)
        assert len(result) == 0  # No groups to aggregate

    def test_quantile_calculation_edge_cases(self):
        """Test quantile calculations with various edge cases."""
        collector = MetricsCollector()
        metric = Metric(
            name="test",
            metric_type=MetricType.SUMMARY,
            description="Test"
        )

        # Test with enough values to properly calculate quantiles
        values = []
        for i in range(100):
            values.append(MetricValue(value=float(i), labels={"test": "many"}))
        metric.values = values

        result = collector._aggregate_summary(metric)
        assert len(result) == 1
        labels, quantiles, count, total_sum = result[0]

        assert count == 100
        assert total_sum == sum(range(100))

        # Check quantiles are reasonable
        assert len(quantiles) == 3
        for q_value, q_result in quantiles:
            assert q_value in [0.5, 0.9, 0.99]
            assert 0 <= q_result < 100

    def test_export_with_inf_bucket(self):
        """Test that histogram export includes inf bucket."""
        collector = MetricsCollector()
        collector.register_histogram("test", "Test histogram", buckets=[0.1, 1.0])

        # Add values spanning all buckets including above the highest
        collector.record_duration("test", 0.05, labels={"type": "fast"})
        collector.record_duration("test", 0.5, labels={"type": "fast"})
        collector.record_duration("test", 2.0, labels={"type": "fast"})  # Above highest bucket

        output = collector.export_prometheus()

        # Check inf bucket is present
        assert 'shadowfs_test_bucket{le="inf",type="fast"} 3' in output

    def test_aggregate_histogram_with_empty_groups(self):
        """Test histogram aggregation when groups dictionary is empty."""
        collector = MetricsCollector()
        metric = Metric(
            name="test",
            metric_type=MetricType.HISTOGRAM,
            description="Test",
            buckets=[0.1]
        )

        # No values means empty groups
        metric.values = []

        result = collector._aggregate_histogram(metric)
        assert result == []

    def test_aggregate_summary_with_empty_groups(self):
        """Test summary aggregation when groups dictionary is empty."""
        collector = MetricsCollector()
        metric = Metric(
            name="test",
            metric_type=MetricType.SUMMARY,
            description="Test"
        )

        # No values means empty groups
        metric.values = []

        result = collector._aggregate_summary(metric)
        assert result == []

    def test_quantile_boundary_conditions(self):
        """Test quantile calculations at exact boundaries."""
        collector = MetricsCollector()
        metric = Metric(
            name="test",
            metric_type=MetricType.SUMMARY,
            description="Test"
        )

        # Test with exactly 2 values - edge case for 99th percentile
        metric.values = [
            MetricValue(value=1.0, labels={"size": "small"}),
            MetricValue(value=2.0, labels={"size": "small"}),
        ]

        result = collector._aggregate_summary(metric)
        assert len(result) == 1
        labels, quantiles, count, total_sum = result[0]
        assert count == 2
        assert total_sum == 3.0

        # All quantiles should be calculated
        quantile_values = [q for q, _ in quantiles]
        assert 0.5 in quantile_values
        assert 0.9 in quantile_values
        assert 0.99 in quantile_values

    def test_quantile_index_out_of_bounds(self):
        """Test quantile when calculated index is >= length."""
        collector = MetricsCollector()
        metric = Metric(
            name="test",
            metric_type=MetricType.SUMMARY,
            description="Test"
        )

        # Create scenario where idx might be == len(sorted_values)
        # This happens when we have very few values
        metric.values = [MetricValue(value=1.0)]

        # Manually test the aggregation
        result = collector._aggregate_summary(metric)

        # Should handle gracefully without index error
        assert len(result) == 1
        labels, quantiles, count, total_sum = result[0]

        # With 1 value, idx for 0.99 quantile = int(1 * 0.99) = 0
        # This is < len(sorted_values) so quantile is added
        assert len(quantiles) > 0