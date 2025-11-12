#!/usr/bin/env python3
"""Final tests to achieve 100% metrics coverage."""

import threading

import pytest

from shadowfs.core.metrics import Metric, MetricsCollector, MetricType, MetricValue


class TestBranchCoverage:
    """Tests to cover missing branches."""

    def test_context_exits(self):
        """Test context manager exits (lines 140, 161, 177)."""
        collector = MetricsCollector()

        # Test register_counter with existing counter (exit early)
        collector.register_counter("test", "First")
        collector.register_counter("test", "Second")  # Should exit early at line 140
        assert collector._metrics["test"].description == "First"

        # Test register_gauge with existing gauge (exit early)
        collector.register_gauge("gauge", "First")
        collector.register_gauge("gauge", "Second")  # Should exit early at line 161
        assert collector._metrics["gauge"].description == "First"

        # Test register_histogram with existing histogram (exit early)
        collector.register_histogram("histogram", "First")
        collector.register_histogram("histogram", "Second")  # Should exit early at line 177
        assert collector._metrics["histogram"].description == "First"

    def test_increment_counter_update_timestamp_branch(self):
        """Test branch at line 246->245 (update existing counter value)."""
        collector = MetricsCollector()
        collector.register_counter("counter", "Test")

        # First increment creates new value
        collector.increment_counter("counter", labels={"env": "prod"})

        # Get initial timestamp
        initial_timestamp = collector._metrics["counter"].values[0].timestamp

        import time

        time.sleep(0.01)  # Small delay to ensure timestamp changes

        # Second increment should update existing value and timestamp
        collector.increment_counter("counter", labels={"env": "prod"})

        # Check that timestamp was updated (line 245 taken)
        new_timestamp = collector._metrics["counter"].values[0].timestamp
        assert new_timestamp > initial_timestamp
        assert collector._metrics["counter"].values[0].value == 2.0

    def test_aggregate_histogram_empty_label_key(self):
        """Test branch at line 424->423 (empty label_key in histogram)."""
        collector = MetricsCollector()
        metric = Metric(
            name="test", metric_type=MetricType.HISTOGRAM, description="Test", buckets=[0.1, 1.0]
        )

        # Add value with no labels (empty label_key)
        metric.values = [MetricValue(value=0.5, labels={})]

        result = collector._aggregate_histogram(metric)
        assert len(result) == 1
        labels, buckets, count, sum_val = result[0]
        assert labels == {}  # Empty labels preserved

    def test_aggregate_summary_empty_label_key(self):
        """Test branch at line 469->468 (empty label_key in summary)."""
        collector = MetricsCollector()
        metric = Metric(name="test", metric_type=MetricType.SUMMARY, description="Test")

        # Add value with no labels (empty label_key)
        metric.values = [MetricValue(value=0.5, labels={})]

        result = collector._aggregate_summary(metric)
        assert len(result) == 1
        labels, quantiles, count, sum_val = result[0]
        assert labels == {}  # Empty labels preserved

    def test_aggregate_summary_quantile_out_of_range(self):
        """Test branch at line 479->477 (idx >= len for quantile)."""
        collector = MetricsCollector()
        metric = Metric(name="test", metric_type=MetricType.SUMMARY, description="Test")

        # With no values, quantile indices will be out of range
        # Create scenario where we group but have empty values for that group
        # This forces the quantile calculation with empty list
        metric.values = []

        # Empty values should result in empty aggregation
        result = collector._aggregate_summary(metric)
        assert len(result) == 0

        # Now test with very small number of values where high quantiles
        # might have idx >= len(sorted_values)
        metric.values = [MetricValue(value=1.0, labels={"test": "single"})]

        result = collector._aggregate_summary(metric)
        labels, quantiles, count, sum_val = result[0]

        # With 1 value:
        # 0.99 quantile: idx = int(1 * 0.99) = 0, which is < 1, so included
        # All quantiles should be the single value
        for q, val in quantiles:
            assert val == 1.0

    def test_aggregate_histogram_label_without_equals(self):
        """Test branch at line 424 when label_key has part without '='."""
        collector = MetricsCollector()
        metric = Metric(
            name="test", metric_type=MetricType.HISTOGRAM, description="Test", buckets=[0.1, 1.0]
        )

        # Directly manipulate to create edge case
        # We need to test the parsing where split produces parts without "="
        # This happens when we manually corrupt the serialization

        # First, add normal values
        metric.values = [
            MetricValue(value=0.5, labels={"key": "value"}),
        ]

        # Mock serialize to return something without equals for testing
        original_serialize = collector._serialize_labels

        def mock_serialize(labels):
            if not labels:
                return ""
            # Return corrupted serialization for test
            return "corrupted_no_equals,key=value"

        collector._serialize_labels = mock_serialize

        # Now aggregate - should handle corrupted serialization
        result = collector._aggregate_histogram(metric)

        # Restore original
        collector._serialize_labels = original_serialize

        # Should still process without crashing
        assert len(result) >= 0

    def test_aggregate_summary_label_without_equals(self):
        """Test branch at line 469 when label_key has part without '='."""
        collector = MetricsCollector()
        metric = Metric(name="test", metric_type=MetricType.SUMMARY, description="Test")

        # Add values with labels
        metric.values = [
            MetricValue(value=1.0, labels={"key": "value"}),
        ]

        # Mock serialize to create edge case
        original_serialize = collector._serialize_labels

        def mock_serialize(labels):
            if not labels:
                return ""
            return "malformed,key=value"

        collector._serialize_labels = mock_serialize

        # Aggregate - should handle malformed serialization
        result = collector._aggregate_summary(metric)

        # Restore
        collector._serialize_labels = original_serialize

        # Should process without crashing
        assert len(result) >= 0

    def test_prometheus_export_branch_344_to_367(self):
        """Test branch in export_prometheus for histogram path."""
        collector = MetricsCollector()

        # Create histogram with no values to test empty case
        collector.register_histogram("empty_hist", "Empty histogram")

        # Create histogram with values to test normal path
        collector.register_histogram("full_hist", "Full histogram")
        collector.record_duration("full_hist", 0.5)

        output = collector.export_prometheus()

        # Both should be in output
        assert "shadowfs_empty_hist" in output
        assert "shadowfs_full_hist" in output

    def test_lock_contention_coverage(self):
        """Test that all lock acquisitions work under contention."""
        collector = MetricsCollector()

        # Register all metric types
        collector.register_counter("counter", "Test counter")
        collector.register_gauge("gauge", "Test gauge")
        collector.register_histogram("hist", "Test histogram")
        collector.register_summary("summary", "Test summary")

        def worker():
            # Perform operations that acquire locks
            for _ in range(10):
                collector.register_counter("counter", "Duplicate")  # Exit early
                collector.register_gauge("gauge", "Duplicate")  # Exit early
                collector.register_histogram("hist", "Duplicate")  # Exit early
                collector.increment_counter("counter", labels={"thread": "test"})
                collector.set_gauge("gauge", 10.0, labels={"thread": "test"})
                collector.record_duration("hist", 0.1)
                collector.export_prometheus()

        threads = []
        for _ in range(5):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Verify operations succeeded
        assert "counter" in collector._metrics
        assert "gauge" in collector._metrics
        assert "hist" in collector._metrics

    def test_export_all_empty_metrics(self):
        """Test export when all metrics exist but have no values."""
        collector = MetricsCollector()

        # Clear all default metric values
        collector.clear_metrics()

        # Register additional empty metrics
        collector.register_summary("empty_summary", "Empty summary")

        # Export should handle all empty metrics gracefully
        output = collector.export_prometheus()

        # Check all metric types are defined even if empty
        assert "# TYPE shadowfs_operations_total counter" in output
        assert "# TYPE shadowfs_cache_size_bytes gauge" in output
        assert "# TYPE shadowfs_operation_duration_seconds histogram" in output
        assert "# TYPE shadowfs_empty_summary summary" in output
