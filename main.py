#!/usr/bin/env -S uv run -s
from rcabench_platform.v2.cli.main import main
from src.trastrainer.register_samplers import register_samplers
if __name__ == "__main__":

    register_samplers()
    main(enable_builtin_algorithms=False)
