"""Register TraStrainer and baseline samplers with RCABench platform."""

from rcabench_platform.v2.samplers.spec import global_sampler_registry

from .baseline_samplers import SieveSampler, SifterSampler, WTSampler
from .trastrainer_sampler import TraStrainerSampler
from .trastrainer_diversity_sampler import TraStrainerDiversitySampler


def register_samplers():
    """Register all TraStrainer and baseline samplers."""
    registry = global_sampler_registry()

    # Register TraStrainer sampler
    registry["trastrainer"] = TraStrainerSampler
    registry["trastrainer_no_metrics"] = TraStrainerDiversitySampler

    # Register baseline samplers
    registry["sifter"] = SifterSampler
    registry["sieve"] = SieveSampler
    registry["wt"] = WTSampler


