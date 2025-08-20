#!/usr/bin/env python3
"""Quick examples of using TraStrainer with uv."""

import json
import subprocess
from pathlib import Path


def run_uv_command(args: list[str]):
    """Run a uv command and return the result."""
    cmd = ["uv", "run"] + args
    print(f"$ {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print(result.stdout)
        else:
            print(f"Error: {result.stderr}")
        return result
    except Exception as e:
        print(f"Exception: {e}")
        return None


def main():
    """Run examples."""
    print("🎯 TraStrainer uv 使用示例\n")

    # 1. 显示帮助
    print("1️⃣ 显示 CLI 帮助:")
    run_uv_command(["trastrainer", "--help"])
    print("\n" + "=" * 60 + "\n")

    # 2. 显示算法信息
    print("2️⃣ 显示算法信息:")
    run_uv_command(["trastrainer", "info"])
    print("\n" + "=" * 60 + "\n")

    # 3. 检查是否存在测试数据
    data_path = Path("data")
    if data_path.exists():
        print("3️⃣ 验证数据文件夹:")
        run_uv_command(["trastrainer", "validate", "data"])
        print("\n" + "=" * 60 + "\n")

        print("4️⃣ 运行采样（JSON 输出）:")
        result = run_uv_command(
            ["trastrainer", "sample", "data", "--rate", "0.1", "--format", "json"]
        )

        if result and result.returncode == 0 and result.stdout.strip():
            try:
                output = json.loads(result.stdout)
                print(
                    f"✅ 采样成功! 从 {output.get('total_traces', 'N/A')} 个 trace 中采样了 {output.get('sampled_traces', 'N/A')} 个"
                )
            except json.JSONDecodeError:
                pass
    else:
        print("3️⃣ 没有找到 data 文件夹，跳过数据验证和采样示例")

    print("\n" + "=" * 60 + "\n")

    # 4. Python API 示例
    print("5️⃣ Python API 示例:")
    run_uv_command(
        [
            "python",
            "-c",
            """
from trastrainer.platform_adapter import TraStrainerAdapter
from trastrainer.data_structures import SamplingConfig

# 创建配置
config = SamplingConfig(
    sampling_rate=0.1,
    warm_up_size=10,
    checkpoints_dir='./checkpoints'
)

print(f'配置创建成功: sampling_rate={config.sampling_rate}')

# 创建适配器
adapter = TraStrainerAdapter()
print('TraStrainerAdapter 创建成功')
        """,
        ]
    )


if __name__ == "__main__":
    main()
