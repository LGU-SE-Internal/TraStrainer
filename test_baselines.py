#!/usr/bin/env python3
"""
Test script for baseline algorithms adapter
"""

import time
from pathlib import Path

from src.trastrainer.baseline_adapter import BaselineAdapter


def test_baseline_algorithm(algorithm: str, sampling_rate: float = 0.05):
    """Test a single baseline algorithm"""
    print(f"\n{'=' * 50}")
    print(f"Testing {algorithm.upper()} Algorithm")
    print(f"{'=' * 50}")

    # Create adapter
    adapter = BaselineAdapter(algorithm, sampling_rate=sampling_rate)
    data_path = Path("test/ts1-ts-route-plan-service-request-replace-method-qtbhzt")

    start_time = time.time()

    try:
        result = adapter(data_path)

        execution_time = time.time() - start_time

        print(f"✅ {algorithm.upper()} completed successfully!")
        print(f"   Algorithm: {result.get('algorithm', 'unknown')}")
        print(f"   Total traces: {result.get('total_traces', 0)}")
        print(f"   Sampled traces: {len(result.get('sampled_trace_ids', []))}")
        print(f"   Target rate: {sampling_rate:.3f}")
        print(f"   Actual rate: {result.get('sampling_rate_achieved', 0):.3f}")
        print(f"   Execution time: {execution_time:.2f}s")
        print(f"   Output: {result.get('output_directory', 'unknown')}")

        return True

    except Exception as e:
        print(f"❌ {algorithm.upper()} failed: {e}")
        return False


def main():
    """Test all baseline algorithms"""
    print("Baseline Algorithms Test Suite")
    print("=" * 60)

    algorithms = ["random", "wt", "sifter", "sieve"]
    sampling_rate = 0.03  # Small rate for faster testing

    results = {}

    for algorithm in algorithms:
        success = test_baseline_algorithm(algorithm, sampling_rate)
        results[algorithm] = success

    # Summary
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")

    successful = [alg for alg, success in results.items() if success]
    failed = [alg for alg, success in results.items() if not success]

    print(f"✅ Working algorithms: {successful}")
    if failed:
        print(f"❌ Failed algorithms: {failed}")
    else:
        print("🎉 All algorithms working perfectly!")

    print(f"\nTotal tested: {len(algorithms)}")
    print(
        f"Success rate: {len(successful)}/{len(algorithms)} ({len(successful) / len(algorithms) * 100:.1f}%)"
    )


if __name__ == "__main__":
    main()
