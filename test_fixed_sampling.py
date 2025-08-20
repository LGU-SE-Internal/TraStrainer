#!/usr/bin/env python3
"""测试修复后的TraStrainer采样逻辑"""

from pathlib import Path

from src.trastrainer.platform_adapter import trastrainer_sampling


def test_fixed_sampling():
    """测试修复后的采样逻辑"""
    print("🔧 测试修复后的TraStrainer采样逻辑")
    print("=" * 60)

    test_data_path = Path(
        "test/ts1-ts-route-plan-service-request-replace-method-qtbhzt"
    )

    # 测试不同采样率
    sampling_rates = [0.05, 0.1, 0.2]

    for rate in sampling_rates:
        print(f"\n🎯 测试采样率: {rate * 100:.0f}%")

        try:
            result = trastrainer_sampling(test_data_path, sampling_rate=rate)

            if "error" in result:
                print(f"   ❌ 采样失败: {result['error']}")
                continue

            print("   ✅ 采样成功!")
            print(f"      总traces: {result['total_traces']}")
            print(f"      采样traces: {len(result['sampled_trace_ids'])}")
            print(f"      目标采样率: {rate * 100:.1f}%")
            print(f"      实际采样率: {result['sampling_rate_achieved'] * 100:.1f}%")
            print(f"      执行时间: {result['execution_time']:.2f}s")

            # 检查输出目录
            output_dir = Path(result.get("output_directory", ""))
            if output_dir.exists():
                import polars as pl

                # 检查保存的文件
                normal_df = pl.read_parquet(output_dir / "normal_traces.parquet")
                abnormal_df = pl.read_parquet(output_dir / "abnormal_traces.parquet")

                normal_count = normal_df.height
                abnormal_count = abnormal_df.height
                normal_unique = (
                    normal_df["trace_id"].n_unique() if normal_count > 0 else 0
                )
                abnormal_unique = (
                    abnormal_df["trace_id"].n_unique() if abnormal_count > 0 else 0
                )

                print(
                    f"      保存的Normal traces: {normal_count} 行 ({normal_unique} 个唯一trace_id)"
                )
                print(
                    f"      保存的Abnormal traces: {abnormal_count} 行 ({abnormal_unique} 个唯一trace_id)"
                )

                if normal_count > 0 and abnormal_count > 0:
                    print("      ✅ 修复成功! Normal和Abnormal期间都有采样数据")
                elif normal_count > 0:
                    print("      ⚠️  只有Normal期间有采样数据")
                elif abnormal_count > 0:
                    print("      ⚠️  只有Abnormal期间有采样数据")
                else:
                    print("      ❌ 没有采样数据")

        except Exception as e:
            print(f"   ❌ 测试失败: {e}")
            import traceback

            traceback.print_exc()

    print("\n💡 修复说明:")
    print("   1. 修改了traces排序：从降序改为升序，优先处理Normal期间")
    print("   2. 移除了早期停止逻辑：现在会处理所有traces而不是只处理部分")
    print("   3. 这样可以确保Normal和Abnormal期间都有机会被采样")


if __name__ == "__main__":
    test_fixed_sampling()
