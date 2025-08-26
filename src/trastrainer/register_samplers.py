"""Register TraStrainer and baseline samplers with RCABench platform."""

from rcabench_platform.v2.samplers.spec import global_sampler_registry

from .baseline_samplers import SieveSampler, SifterSampler, WTSampler
from .trastrainer_sampler import TraStrainerSampler


def register_samplers():
    """Register all TraStrainer and baseline samplers."""
    registry = global_sampler_registry()

    # Register TraStrainer sampler
    registry["trastrainer"] = TraStrainerSampler

    # Register baseline samplers
    registry["sifter"] = SifterSampler
    registry["sieve"] = SieveSampler
    registry["wt"] = WTSampler

    print("Registered samplers: trastrainer, sifter, sieve, wt")


# Auto-register when module is imported
register_samplers()
