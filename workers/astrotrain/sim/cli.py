"""
AstroTrain Simulation CLI.

Simple command-line interface for running pre-built scenarios
and inspecting results.

Usage:
    python -m workers.astrotrain.sim.cli --scenario beer_game --runs 500 --periods 52
    python -m workers.astrotrain.sim.cli --scenario smb_distributor
    python -m workers.astrotrain.sim.cli --scenario multi_echelon --runs 200
"""

from __future__ import annotations

import argparse
import sys

from . import scenarios
from .engine import SimulationEngine
from .reporter import SimReporter

SCENARIOS = {
    "beer_game": scenarios.beer_game,
    "smb_distributor": scenarios.smb_distributor,
    "multi_echelon": scenarios.multi_echelon,
}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="astrotrain-sim",
        description="AstroTrain Supply Chain Simulation Engine",
    )
    parser.add_argument(
        "--scenario",
        required=True,
        choices=list(SCENARIOS.keys()),
        help="Pre-built scenario template to run",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=None,
        help="Number of Monte Carlo runs (overrides scenario default)",
    )
    parser.add_argument(
        "--periods",
        type=int,
        default=None,
        help="Number of simulation periods (overrides scenario default)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Skip saving results to JSON",
    )

    args = parser.parse_args(argv)

    # Load and optionally override scenario config
    config = SCENARIOS[args.scenario]()
    if args.runs is not None:
        config.num_runs = args.runs
    if args.periods is not None:
        config.periods = args.periods

    print(f"Running scenario: {config.name}")
    print(f"  Echelons: {', '.join(e.name for e in config.echelons)}")
    print(f"  Periods: {config.periods} | Runs: {config.num_runs}")
    print(f"  Demand: {config.demand_pattern} (mean={config.demand_mean}, std={config.demand_std})")
    if args.seed is not None:
        print(f"  Seed: {args.seed}")
    print()

    engine = SimulationEngine(config, seed=args.seed)
    result = engine.run()

    reporter = SimReporter(result)

    # Print summary
    print(reporter.summary())
    print()

    # Print KPI table
    print(reporter.kpi_table())

    # Save JSON
    if not args.no_save:
        path = reporter.to_json()
        print(f"\nResults saved to: {path}")


if __name__ == "__main__":
    main()
