# TraStrainer with uv

这个项目使用 `uv` 作为包管理器。以下是使用说明：

## 安装项目

```bash
# 安装项目及其依赖
uv sync

# 或者使用开发模式安装
uv sync --dev
```

## 运行 CLI

### 使用 uv run

```bash
# 显示帮助信息
uv run trastrainer --help

# 显示算法信息
uv run trastrainer info

# 验证数据文件夹
uv run trastrainer validate data/

# 执行采样
uv run trastrainer sample data/ --rate 0.1 --verbose

# 不同输出格式
uv run trastrainer sample data/ --rate 0.1 --format json
uv run trastrainer sample data/ --rate 0.1 --format csv
uv run trastrainer sample data/ --rate 0.1 --format simple
```

### 直接运行模块

```bash
# 也可以直接运行 CLI 模块
uv run python -m trastrainer.cli --help
uv run python -m trastrainer.cli sample data/ --rate 0.1
```

## 开发模式

### 运行测试

```bash
# 运行集成测试
uv run python test_polars.py

# 运行示例
uv run python examples/polars_usage.py
```

### 代码格式化和检查

```bash
# 使用 ruff 格式化代码
uv run ruff format src/

# 代码检查
uv run ruff check src/

# 类型检查
uv run pyright src/
```

## 作为 Python 包使用

```bash
# 在 Python 脚本中使用
uv run python -c "
from trastrainer.platform_adapter import trastrainer_sampling
result = trastrainer_sampling('data/', 0.1)
print(result)
"
```

## 构建和分发

```bash
# 构建包
uv build

# 安装到其他环境
pip install dist/TraStrainer-*.whl
```

## 环境管理

```bash
# 查看当前环境
uv python info

# 使用特定 Python 版本
uv python use 3.13

# 查看已安装的包
uv tree
```

## 添加新依赖

```bash
# 添加运行时依赖
uv add package_name

# 添加开发依赖
uv add --dev package_name

# 从 requirements.txt 添加
uv add -r requirements.txt
```
