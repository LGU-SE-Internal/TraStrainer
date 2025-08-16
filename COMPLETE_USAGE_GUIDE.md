# TraStrainer 完整运行指南

## 环境准备

1. **确保 uv 已安装并且项目依赖已同步**
```bash
uv sync
```

## 完整运行流程

### 1. 验证测试数据

首先验证测试数据是否完整：

```bash
uv run trastrainer validate "test/ts1-ts-route-plan-service-request-replace-method-qtbhzt"
```

### 2. 查看算法信息

了解 TraStrainer 算法的详细信息：

```bash
uv run trastrainer info
```

### 3. 执行采样

执行不同采样率的采样：

```bash
# 1% 采样率（推荐用于大数据集）
uv run trastrainer sample "test/ts1-ts-route-plan-service-request-replace-method-qtbhzt" --rate 0.01 --verbose --format json

# 5% 采样率（中等采样）
uv run trastrainer sample "test/ts1-ts-route-plan-service-request-replace-method-qtbhzt" --rate 0.05 --verbose --format json

# 10% 采样率（高采样率）
uv run trastrainer sample "test/ts1-ts-route-plan-service-request-replace-method-qtbhzt" --rate 0.1 --verbose --format json
```

### 4. 查看结果

采样结果会保存到：
```
test/ts1-ts-route-plan-service-request-replace-method-qtbhzt/sampled/trastrainer/
```

包含的文件：
- `normal_traces.parquet` - 正常时期的采样trace
- `abnormal_traces.parquet` - 异常时期的采样trace  
- `normal_metrics.parquet` - 完整的正常时期metrics
- `abnormal_metrics.parquet` - 完整的异常时期metrics
- `env.json` - 环境配置（时间范围等）
- 其他原始文件的副本

### 5. 验证采样结果

验证采样后的数据：

```bash
uv run trastrainer validate "test/ts1-ts-route-plan-service-request-replace-method-qtbhzt/sampled/trastrainer"
```

## 输出格式说明

### JSON 格式（默认）
```json
{
  "sampling_rate_target": 0.05,
  "sampling_rate_achieved": 0.048,
  "total_traces": 1974,
  "sampled_traces": 95,
  "execution_time": 12.34,
  "sampled_trace_ids": ["trace_id_1", "trace_id_2", "..."],
  "output_directory": "path/to/sampled/trastrainer"
}
```

### CSV 格式
```bash
uv run trastrainer sample "test/..." --rate 0.05 --format csv
```

### Simple 格式（向后兼容）
```bash
uv run trastrainer sample "test/..." --rate 0.05 --format simple
```

## 使用任务运行器

您也可以使用任务运行器：

```bash
# 查看可用任务
uv run python tasks.py help

# 运行示例
uv run python tasks.py example

# 验证数据
uv run python tasks.py validate
```

## Python API 使用

如果需要在 Python 代码中使用：

```python
from pathlib import Path
from trastrainer.platform_adapter import trastrainer_sampling

# 执行采样
result = trastrainer_sampling(
    input_folder=Path("test/ts1-ts-route-plan-service-request-replace-method-qtbhzt"),
    sampling_rate=0.05
)

print(f"采样了 {len(result['sampled_trace_ids'])} 个trace")
print(f"结果保存在: {result['output_directory']}")
```

## 故障排除

### 常见问题

1. **找不到数据文件**
   - 确保路径正确
   - 检查必需文件是否存在（使用 validate 命令）

2. **内存不足**
   - 降低采样率
   - 分批处理数据

3. **模型checkpoints缺失**
   - 确保 `checkpoints/` 目录存在
   - 检查模型文件是否完整

### 调试模式

添加 `--verbose` 标志获取详细日志：
```bash
uv run trastrainer sample "test/..." --rate 0.05 --verbose
```
