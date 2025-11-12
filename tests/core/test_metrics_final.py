#!/usr/bin/env python3
"""Final tests to complete 100% metrics coverage."""

import time

import pytest

from shadowfs.core.metrics import Metric, MetricsCollector, MetricType, MetricValue


class TestFinalBranchCoverage:
    """Tests for final branch coverage."""

    def test_register_histogram_early_return(self):
        """Force early return from register_histogram (line 177->exit)."""
        collector = MetricsCollector()

        # First registration succeeds
        collector.register_histogram("test_hist", "First", buckets=[0.1, 1.0])

        # Verify it was registered
        assert "test_hist" in collector._metrics
        assert collector._metrics["test_hist"].description == "First"
        assert collector._metrics["test_hist"].buckets == [0.1, 1.0]

        # Second registration should return early (line 177->exit)
        # The key is already in the dict, so it exits immediately
        collector.register_histogram("test_hist", "Second", buckets=[0.5, 2.0])

        # Verify original is unchanged
        assert collector._metrics["test_hist"].description == "First"
        assert collector._metrics["test_hist"].buckets == [0.1, 1.0]

    def test_increment_counter_existing_value_update(self):
        """Test updating existing counter value (line 246->245)."""
        collector = MetricsCollector()
        collector.register_counter("test_counter", "Test")

        # First increment creates value
        collector.increment_counter("test_counter", labels={"env": "prod"}, value=1.0)
        assert len(collector._metrics["test_counter"].values) == 1
        assert collector._metrics["test_counter"].values[0].value == 1.0

        # Store initial timestamp
        initial_ts = collector._metrics["test_counter"].values[0].timestamp

        # Small delay to ensure timestamp changes
        time.sleep(0.001)

        # Second increment with same labels should update existing (line 245 executed)
        collector.increment_counter("test_counter", labels={"env": "prod"}, value=2.0)

        # Still only one value entry, but value increased
        assert len(collector._metrics["test_counter"].values) == 1
        assert collector._metrics["test_counter"].values[0].value == 3.0
        # Timestamp should be updated
        assert collector._metrics["test_counter"].values[0].timestamp > initial_ts

    def test_export_histogram_with_and_without_values(self):
        """Test histogram export branches (line 344->367)."""
        collector = MetricsCollector()

        # Register histogram and immediately export (no values)
        collector.register_histogram("empty_hist", "Empty", buckets=[0.1])
        output1 = collector.export_prometheus()

        # Should have type definition but no bucket values
        assert "# TYPE shadowfs_empty_hist histogram" in output1
        assert "shadowfs_empty_hist_bucket" not in output1  # No buckets exported when empty

        # Add values and export again
        collector.record_duration("empty_hist", 0.05)
        output2 = collector.export_prometheus()

        # Now should have bucket values
        assert "shadowfs_empty_hist_bucket" in output2
        assert "shadowfs_empty_hist_count" in output2
        assert "shadowfs_empty_hist_sum" in output2

    def test_aggregate_summary_quantile_boundary(self):
        """Test quantile index boundary condition (line 479->477)."""
        collector = MetricsCollector()
        metric = Metric(name="test", metric_type=MetricType.SUMMARY, description="Test")

        # With 0 values, all quantile calculations skip (empty sorted_values)
        metric.values = []
        result = collector._aggregate_summary(metric)
        assert len(result) == 0

        # With 1 value, test quantile index calculations
        metric.values = [MetricValue(value=5.0, labels={"test": "one"})]
        result = collector._aggregate_summary(metric)
        assert len(result) == 1
        labels, quantiles, count, sum_val = result[0]

        # For 1 value:
        # 0.5 quantile: idx = int(1 * 0.5) = 0, valid
        # 0.9 quantile: idx = int(1 * 0.9) = 0, valid
        # 0.99 quantile: idx = int(1 * 0.99) = 0, valid
        # All should be included
        assert len(quantiles) == 3
        for q_val, q_result in quantiles:
            assert q_result == 5.0  # All quantiles are the single value

        # Test with 2 values to check different idx calculations
        metric.values = [
            MetricValue(value=1.0, labels={"test": "two"}),
            MetricValue(value=9.0, labels={"test": "two"}),
        ]
        result = collector._aggregate_summary(metric)
        labels, quantiles, count, sum_val = result[0]

        # For 2 values (sorted: [1.0, 9.0]):
        # 0.5 quantile: idx = int(2 * 0.5) = 1, valid (returns 9.0)
        # 0.9 quantile: idx = int(2 * 0.9) = 1, valid (returns 9.0)
        # 0.99 quantile: idx = int(2 * 0.99) = 1, valid (returns 9.0)
        assert len(quantiles) == 3

    def test_edge_case_coverage(self):
        """Additional edge case tests for complete coverage."""
        collector = MetricsCollector()

        # Test registering metrics that already exist
        # These should all return early without modifying the metrics
        collector.register_histogram("operation_duration_seconds", "Duplicate")
        orig_desc = collector._metrics["operation_duration_seconds"].description
        assert orig_desc != "Duplicate"  # Original description preserved

        # Test with very large number of values to ensure quantiles work
        collector.register_summary("large_summary", "Large dataset")
        for i in range(1000):
            collector.record_duration("large_summary", float(i) / 100.0, labels={"size": "large"})

        # Export should handle large datasets
        output = collector.export_prometheus()
        assert "shadowfs_large_summary" in output
        assert 'shadowfs_large_summary_count{size="large"} 1000' in output

    def test_concurrent_registration(self):
        """Test concurrent metric registration to ensure thread safety."""
        import threading

        collector = MetricsCollector()

        def register_histogram():
            # All threads try to register the same histogram
            collector.register_histogram(
                "concurrent_hist", "Concurrent test", buckets=[0.1, 0.5, 1.0]
            )

        threads = []
        for _ in range(10):
            t = threading.Thread(target=register_histogram)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Should have exactly one histogram registered
        assert "concurrent_hist" in collector._metrics
        assert collector._metrics["concurrent_hist"].metric_type == MetricType.HISTOGRAM
        assert collector._metrics["concurrent_hist"].buckets == [0.1, 0.5, 1.0]
