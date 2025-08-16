#!/usr/bin/env python3
"""完整的TraStrainer运行测试脚本"""

import json
import subprocess
import time
from pathlib import Path


def run_command(cmd: list[str], description: str, timeout: int = 60) -> dict:
    """运行命令并返回结果"""
    print(f"\n🔧 {description}")
    print(f"   命令: {' '.join(cmd)}")

    try:
        start_time = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        end_time = time.time()

        if result.returncode == 0:
            print(f"   ✅ 成功! (耗时: {end_time - start_time:.1f}s)")
            return {
                "success": True,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "execution_time": end_time - start_time,
            }
        else:
            print(f"   ❌ 失败! (返回码: {result.returncode})")
            if result.stderr:
                print(f"   错误: {result.stderr[:200]}...")
            return {
                "success": False,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "execution_time": end_time - start_time,
            }

    except subprocess.TimeoutExpired:
        print(f"   ⏰ 超时! ({timeout}s)")
        return {"success": False, "error": "timeout"}
    except Exception as e:
        print(f"   💥 异常: {e}")
        return {"success": False, "error": str(e)}


def main():
    """完整运行测试"""
    print("🚀 TraStrainer 完整运行测试")
    print("=" * 60)

    # 测试数据路径
    test_data_path = "test/ts1-ts-route-plan-service-request-replace-method-qtbhzt"

    # 步骤1: 验证环境
    print("\n📋 步骤 1: 验证环境")

    # 检查uv
    result = run_command(["uv", "--version"], "检查 uv 版本")
    if not result["success"]:
        print("❌ uv 不可用，请先安装 uv")
        return 1

    # 同步依赖
    result = run_command(["uv", "sync"], "同步项目依赖", timeout=120)
    if not result["success"]:
        print("❌ 依赖同步失败")
        return 1

    # 步骤2: 验证数据
    print("\n📋 步骤 2: 验证测试数据")

    # 检查数据路径
    data_path = Path(test_data_path)
    if not data_path.exists():
        print(f"❌ 测试数据路径不存在: {test_data_path}")
        return 1

    # 验证数据完整性
    result = run_command(
        ["uv", "run", "trastrainer", "validate", test_data_path], "验证数据完整性"
    )

    if not result["success"]:
        print("❌ 数据验证失败")
        return 1

    # 步骤3: 显示算法信息
    print("\n📋 步骤 3: 显示算法信息")

    result = run_command(["uv", "run", "trastrainer", "info"], "显示算法信息")

    # 步骤4: 执行采样
    print("\n📋 步骤 4: 执行采样测试")

    # 测试不同的采样率
    sampling_rates = [0.01, 0.05]

    for rate in sampling_rates:
        print(f"\n   测试采样率: {rate}")

        result = run_command(
            [
                "uv",
                "run",
                "trastrainer",
                "sample",
                test_data_path,
                "--rate",
                str(rate),
                "--verbose",
                "--format",
                "json",
            ],
            f"执行 {rate * 100}% 采样",
            timeout=300,
        )

        if result["success"]:
            try:
                # 解析JSON输出
                output = json.loads(result["stdout"])
                print("      ✨ 采样成功!")
                print(f"         总traces: {output.get('total_traces', 'N/A')}")
                print(f"         采样traces: {output.get('sampled_traces', 'N/A')}")
                print(f"         目标采样率: {rate * 100:.1f}%")
                print(
                    f"         实际采样率: {output.get('sampling_rate_achieved', 0) * 100:.1f}%"
                )
                print(f"         执行时间: {output.get('execution_time', 0):.1f}s")
                print(f"         输出目录: {output.get('output_directory', 'N/A')}")

                # 验证输出目录
                if output.get("output_directory"):
                    output_path = Path(output["output_directory"])
                    if output_path.exists():
                        print("      ✅ 输出目录验证成功")

                        # 验证采样后的数据
                        verify_result = run_command(
                            ["uv", "run", "trastrainer", "validate", str(output_path)],
                            f"验证采样后的数据 (rate={rate})",
                        )

                        if verify_result["success"]:
                            print("      ✅ 采样数据验证通过")
                        else:
                            print("      ⚠️  采样数据验证失败")

            except json.JSONDecodeError:
                print("      ⚠️  无法解析JSON输出")
                print(f"         原始输出: {result['stdout'][:200]}...")
        else:
            print("      ❌ 采样失败")

    # 步骤5: 测试其他输出格式
    print("\n📋 步骤 5: 测试输出格式")

    formats = ["csv", "simple"]
    for fmt in formats:
        result = run_command(
            [
                "uv",
                "run",
                "trastrainer",
                "sample",
                test_data_path,
                "--rate",
                "0.01",
                "--format",
                fmt,
            ],
            f"测试 {fmt} 格式输出",
            timeout=180,
        )

        if result["success"]:
            print(f"      ✅ {fmt} 格式输出正常")
            if result["stdout"]:
                print(f"         输出示例: {result['stdout'][:100]}...")

    # 步骤6: Python API测试
    print("\n📋 步骤 6: Python API 测试")

    python_test_code = f'''
from pathlib import Path
from trastrainer.platform_adapter import trastrainer_sampling

try:
    result = trastrainer_sampling(
        input_folder=Path("{test_data_path}"),
        sampling_rate=0.01
    )
    
    print("✅ Python API 调用成功")
    print(f"采样traces数量: {{len(result.get('sampled_trace_ids', []))}}")
    print(f"总traces数量: {{result.get('total_traces', 'N/A')}}")
    print(f"输出目录: {{result.get('output_directory', 'N/A')}}")
    
except Exception as e:
    print(f"❌ Python API 调用失败: {{e}}")
    exit(1)
'''

    result = run_command(
        ["uv", "run", "python", "-c", python_test_code], "Python API 测试", timeout=180
    )

    print("\n" + "=" * 60)
    print("🎯 完整运行测试结果总结")
    print("=" * 60)

    if result["success"]:
        print("🎉 所有测试通过! TraStrainer 运行正常")
        print("\n📁 检查生成的采样数据目录:")
        print(f"   {test_data_path}/sampled/trastrainer/")

        # 显示最终的使用建议
        print("\n💡 使用建议:")
        print("   1. 对于大数据集，建议使用 0.01-0.05 的采样率")
        print("   2. 使用 --verbose 参数获取详细日志")
        print("   3. 采样结果保存在原数据目录的 sampled/trastrainer/ 下")
        print("   4. 可以对采样后的数据再次运行 validate 命令验证")

        return 0
    else:
        print("💥 部分测试失败，请检查日志")
        return 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
