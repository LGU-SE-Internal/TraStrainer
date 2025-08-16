"""Typer CLI application for TraStrainer."""

from pathlib import Path
from typing import Optional

import typer
from rcabench_platform.v2.logging import logger

from .platform_adapter import trastrainer_sampling

app = typer.Typer(
    name="trastrainer",
    help="TraStrainer: Adaptive trace sampling with system runtime state",
    no_args_is_help=True,
)


@app.command()
def sample(
    data_path: Path = typer.Argument(
        ...,
        help="Path to folder containing trace and metric data (Parquet files)",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
    sampling_rate: float = typer.Option(
        0.1,
        "--rate",
        "-r",
        help="Target sampling rate (between 0 and 1)",
        min=0.001,
        max=1.0,
    ),
    checkpoints_dir: Optional[Path] = typer.Option(
        "./checkpoints",
        "--checkpoints",
        "-c",
        help="Directory containing model checkpoints",
    ),
    warm_up_size: int = typer.Option(
        10,
        "--warm-up",
        "-w",
        help="Number of traces to process before applying sampling logic",
        min=1,
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose logging"
    ),
    output_format: str = typer.Option(
        "json",
        "--format",
        "-f",
        help="Output format (json, csv, or simple)",
        case_sensitive=False,
    ),
):
    """
    Run TraStrainer adaptive trace sampling.

    This command loads trace and metric data from Parquet files and applies
    the TraStrainer algorithm to select a representative sample of traces
    based on both system metrics and trace diversity.
    """
    # Configure logging
    if verbose:
        # logger.setLevel("DEBUG")  # This doesn't work with loguru
        logger.info("Verbose logging enabled")

    logger.info("Starting TraStrainer sampling")
    logger.info(f"Data path: {data_path}")
    logger.info(f"Sampling rate: {sampling_rate}")

    try:
        # Run TraStrainer sampling
        result = trastrainer_sampling(
            input_folder=data_path, sampling_rate=sampling_rate
        )

        if "error" in result:
            logger.error(f"Sampling failed: {result['error']}")
            typer.echo(f"Error: {result['error']}", err=True)
            raise typer.Exit(1)

        # Output results based on format
        if output_format.lower() == "simple":
            # Simple format for backward compatibility
            typer.echo(
                f"sampling_rate:{sampling_rate}, sampling trace_ids:{result['sampled_trace_ids']}"
            )

        elif output_format.lower() == "csv":
            # CSV format
            typer.echo("trace_id")
            for trace_id in result["sampled_trace_ids"]:
                typer.echo(trace_id)

        else:
            # JSON format (default)
            import json

            output = {
                "sampling_rate_target": sampling_rate,
                "sampling_rate_achieved": result["sampling_rate_achieved"],
                "total_traces": result["total_traces"],
                "sampled_traces": len(result["sampled_trace_ids"]),
                "execution_time": result["execution_time"],
                "sampled_trace_ids": result["sampled_trace_ids"],
                "output_directory": result.get("output_directory", None),
            }
            typer.echo(json.dumps(output, indent=2))

        logger.info("Sampling completed successfully")
        logger.info(
            f"Sampled {len(result['sampled_trace_ids'])} out of {result['total_traces']} traces"
        )
        logger.info(f"Achieved sampling rate: {result['sampling_rate_achieved']:.4f}")

        # Show output directory if available
        if "output_directory" in result:
            logger.info(f"Results saved to: {result['output_directory']}")
            typer.echo(f"\n✅ Results saved to: {result['output_directory']}")

    except Exception as e:
        logger.error(f"TraStrainer failed: {e}")
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def info():
    """Display information about TraStrainer algorithm."""
    info_text = """
TraStrainer: Adaptive Trace Sampling Algorithm

TraStrainer is an online sampler that considers both system runtime state 
and trace diversity when selecting traces for analysis. It uses:

1. System Bias Filter: Analyzes system metrics to identify anomalous behavior
2. Diversity Bias Filter: Ensures structural diversity in sampled traces  
3. Dynamic Voting: Combines both filters using adaptive AND/OR logic

Key Features:
- Adaptive sampling based on system metrics and trace structure
- Machine learning-based metric prediction for weight computation
- Configurable sampling rates and warm-up periods
- Support for both normal and anomalous time periods
- Backward compatibility with legacy data formats

Data Requirements:
- Traces: Parquet files with columns: time, trace_id, span_id, parent_span_id, 
  service_name, span_name, duration, attr.*
- Metrics: Parquet files with columns: time, metric, value, service_name, attr.*
- Environment: env.json with time range definitions

For more information, see the documentation or run with --help.
    """
    typer.echo(info_text)


@app.command()
def validate(
    data_path: Path = typer.Argument(
        ...,
        help="Path to folder containing data to validate",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
):
    """Validate that the data folder contains required files and structure."""

    logger.info(f"Validating data folder: {data_path}")

    required_files = [
        "env.json",
        "normal_traces.parquet",
        "abnormal_traces.parquet",
        "normal_metrics.parquet",
        "abnormal_metrics.parquet",
    ]

    missing_files = []
    for file_name in required_files:
        file_path = data_path / file_name
        if not file_path.exists():
            missing_files.append(file_name)

    if missing_files:
        typer.echo(f"❌ Missing required files: {', '.join(missing_files)}", err=True)
        typer.echo("\nRequired files for TraStrainer:")
        for file_name in required_files:
            status = "✅" if file_name not in missing_files else "❌"
            typer.echo(f"  {status} {file_name}")
        raise typer.Exit(1)
    else:
        typer.echo("✅ All required files found!")

        # Try to load and validate structure
        try:
            from .polar_loader import PolarDataPreprocessor

            preprocessor = PolarDataPreprocessor()
            traces, metrics = preprocessor.load_data(data_path)

            typer.echo("✅ Data loaded successfully!")
            typer.echo(f"  Traces: {len(traces)}")
            typer.echo(f"  Metric series: {len(metrics)}")

        except Exception as e:
            typer.echo(f"❌ Data validation failed: {e}", err=True)
            raise typer.Exit(1)


if __name__ == "__main__":
    app()
