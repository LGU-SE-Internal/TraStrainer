"""Basic tests for the restructured TraStrainer package."""

import csv
import os
import tempfile

from src.trastrainer.algorithm import SimilarityCalculator
from src.trastrainer.data_structures import SamplingConfig, TraceData, TraceSpan
from src.trastrainer.preprocessor import DataPreprocessor


class TestDataStructures:
    """Test data structure classes."""

    def test_trace_span_creation(self):
        """Test TraceSpan creation and properties."""
        span = TraceSpan(
            trace_id="test-trace",
            span_id="test-span",
            parent_id="root",
            service_name="test-service",
            operation_name="test-op",
            start_time="2024-01-01 10:00:00",
            end_time="2024-01-01 10:00:01",
            duration=1000000,
        )

        assert span.trace_id == "test-trace"
        assert span.is_root == True
        assert span.status == "success"  # default value

    def test_trace_data_properties(self):
        """Test TraceData properties."""
        span1 = TraceSpan(
            trace_id="test-trace",
            span_id="span-1",
            parent_id="root",
            service_name="svc",
            operation_name="op",
            start_time="2024-01-01 10:00:00",
            end_time="2024-01-01 10:00:01",
            duration=1000000,
        )

        span2 = TraceSpan(
            trace_id="test-trace",
            span_id="span-2",
            parent_id="span-1",
            service_name="svc",
            operation_name="op",
            start_time="2024-01-01 10:00:01",
            end_time="2024-01-01 10:00:02",
            duration=1000000,
        )

        trace = TraceData(trace_id="test-trace", spans=[span1, span2])

        assert trace.root_span == span1
        assert trace.start_time == "2024-01-01 10:00:00"
        assert trace.end_time == "2024-01-01 10:00:02"

    def test_sampling_config(self):
        """Test SamplingConfig creation and defaults."""
        config = SamplingConfig(budget_sample_rate=0.1)

        assert config.budget_sample_rate == 0.1
        assert config.window_size == 10  # 1/0.1
        assert config.warm_up_size == 10


class TestSimilarityCalculator:
    """Test similarity calculation functions."""

    def test_jaccard_similarity(self):
        """Test Jaccard similarity computation."""
        seq1 = ["a", "b", "c"]
        seq2 = ["b", "c", "d"]

        similarity = SimilarityCalculator.compute_jaccard_similarity(seq1, seq2)

        # Intersection: {b, c} = 2 elements
        # Union: {a, b, c, d} = 4 elements
        # Jaccard = 2/4 = 0.5
        assert abs(similarity - 0.5) < 0.01

    def test_jaccard_identical_sequences(self):
        """Test Jaccard similarity for identical sequences."""
        seq1 = ["a", "b", "c"]
        seq2 = ["a", "b", "c"]

        similarity = SimilarityCalculator.compute_jaccard_similarity(seq1, seq2)
        assert abs(similarity - 1.0) < 0.01

    def test_jaccard_disjoint_sequences(self):
        """Test Jaccard similarity for disjoint sequences."""
        seq1 = ["a", "b"]
        seq2 = ["c", "d"]

        similarity = SimilarityCalculator.compute_jaccard_similarity(seq1, seq2)
        assert abs(similarity - 0.0) < 0.01


class TestDataPreprocessor:
    """Test data preprocessing functionality."""

    def test_time_utils(self):
        """Test timestamp utility functions."""
        from src.trastrainer.preprocessor import TimeUtils

        # Test timestamp conversion
        dt_str = TimeUtils.timestamp_to_datetime(
            "1640995200"
        )  # 2022-01-01 00:00:00 UTC
        assert "2022" in dt_str

        # Test future datetime calculation
        future = TimeUtils.future_datetime("2024-01-01 10:00:00", 30)
        assert future == "2024-01-01 10:30:00"

    def create_test_csv_data(self):
        """Create temporary test CSV files."""
        # Create temporary directory
        temp_dir = tempfile.mkdtemp()

        # Create test traces CSV
        traces_path = os.path.join(temp_dir, "traces.csv")
        with open(traces_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "TraceId",
                    "SpanId",
                    "ParentSpanId",
                    "ServiceName",
                    "SpanName",
                    "Timestamp",
                    "Duration",
                ]
            )
            writer.writerow(
                [
                    "trace-1",
                    "span-1",
                    "",
                    "user-service",
                    "get_user",
                    "2024-01-01 10:00:00",
                    "1000000",
                ]
            )
            writer.writerow(
                [
                    "trace-1",
                    "span-2",
                    "span-1",
                    "db-service",
                    "query",
                    "2024-01-01 10:00:00",
                    "500000",
                ]
            )

        # Create test metrics CSV
        metrics_path = os.path.join(temp_dir, "metrics.csv")
        with open(metrics_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                ["MetricName", "ServiceName", "TimeUnix", "Value", "ResourceAttributes"]
            )
            writer.writerow(
                [
                    "k8s.pod.cpu.usage",
                    "user-service",
                    "2024-01-01 10:00:00",
                    "0.5",
                    "{}",
                ]
            )
            writer.writerow(
                [
                    "k8s.pod.memory.usage",
                    "user-service",
                    "2024-01-01 10:00:00",
                    "100.0",
                    "{}",
                ]
            )

        return temp_dir

    def test_load_data(self):
        """Test data loading functionality."""
        temp_dir = self.create_test_csv_data()

        try:
            preprocessor = DataPreprocessor()
            traces, metrics = preprocessor.load_data(temp_dir)

            # Should have loaded at least some data
            assert isinstance(traces, dict)
            assert isinstance(metrics, dict)

        finally:
            # Cleanup
            import shutil

            shutil.rmtree(temp_dir)


def test_basic_integration():
    """Test basic integration without real data."""
    from src.trastrainer.algorithm import TraStrainerAlgorithm

    # Create minimal test data
    span = TraceSpan(
        trace_id="test-trace",
        span_id="test-span",
        parent_id="root",
        service_name="test-service",
        operation_name="test-op",
        start_time="2024-01-01 10:00:00",
        end_time="2024-01-01 10:00:01",
        duration=1000000,
    )

    trace = TraceData(trace_id="test-trace", spans=[span])
    traces = {"test-trace": trace}
    metrics = {("test-service", "cpu"): [{"date": "2024-01-01 10:00:00", "value": 0.5}]}

    config = SamplingConfig(budget_sample_rate=1.0)  # Sample everything
    algorithm = TraStrainerAlgorithm(config)

    # This should work without crashing
    result = algorithm.run(traces, metrics)

    assert result.actual_sample_count >= 0
    assert result.total_traces_processed >= 0


if __name__ == "__main__":
    # Run basic tests
    test_basic_integration()
    print("Basic integration test passed!")

    # Run data structure tests
    ds_tests = TestDataStructures()
    ds_tests.test_trace_span_creation()
    ds_tests.test_trace_data_properties()
    ds_tests.test_sampling_config()
    print("Data structure tests passed!")

    # Run similarity tests
    sim_tests = TestSimilarityCalculator()
    sim_tests.test_jaccard_similarity()
    sim_tests.test_jaccard_identical_sequences()
    sim_tests.test_jaccard_disjoint_sequences()
    print("Similarity tests passed!")

    print("All tests passed!")
