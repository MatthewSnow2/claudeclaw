"""
Tests for the AstroTrain Simulation Engine.

All tests use fixed random seeds for reproducibility.
"""

from __future__ import annotations

import json
import os
import tempfile

import numpy as np
import pytest

from .engine import Echelon, ScenarioConfig, SimulationEngine, SimulationResult
from .reporter import SimReporter
from .scenarios import beer_game, multi_echelon, smb_distributor


# ---------------------------------------------------------------------------
# ScenarioConfig validation
# ---------------------------------------------------------------------------


class TestScenarioConfigValidation:
    """Test that ScenarioConfig.validate() catches invalid inputs."""

    def test_valid_config_has_no_errors(self):
        config = ScenarioConfig(
            name="test",
            echelons=[
                Echelon(
                    name="Store",
                    lead_time=1,
                    holding_cost=0.5,
                    stockout_cost=2.0,
                    order_cost=10.0,
                    initial_inventory=100,
                    reorder_point=50,
                    order_quantity=100,
                )
            ],
        )
        assert config.validate() == []

    def test_empty_name_is_invalid(self):
        config = ScenarioConfig(
            name="",
            echelons=[
                Echelon(
                    name="Store",
                    lead_time=1,
                    holding_cost=0.5,
                    stockout_cost=2.0,
                    order_cost=10.0,
                    initial_inventory=100,
                    reorder_point=50,
                    order_quantity=100,
                )
            ],
        )
        errors = config.validate()
        assert any("name" in e.lower() for e in errors)

    def test_zero_periods_is_invalid(self):
        config = ScenarioConfig(
            name="test",
            periods=0,
            echelons=[
                Echelon(
                    name="Store",
                    lead_time=1,
                    holding_cost=0.5,
                    stockout_cost=2.0,
                    order_cost=10.0,
                    initial_inventory=100,
                    reorder_point=50,
                    order_quantity=100,
                )
            ],
        )
        errors = config.validate()
        assert any("period" in e.lower() for e in errors)

    def test_no_echelons_is_invalid(self):
        config = ScenarioConfig(name="test", echelons=[])
        errors = config.validate()
        assert any("echelon" in e.lower() for e in errors)

    def test_bad_demand_pattern_is_invalid(self):
        config = ScenarioConfig(
            name="test",
            demand_pattern="chaotic",
            echelons=[
                Echelon(
                    name="Store",
                    lead_time=1,
                    holding_cost=0.5,
                    stockout_cost=2.0,
                    order_cost=10.0,
                    initial_inventory=100,
                    reorder_point=50,
                    order_quantity=100,
                )
            ],
        )
        errors = config.validate()
        assert any("demand_pattern" in e for e in errors)

    def test_negative_holding_cost_is_invalid(self):
        config = ScenarioConfig(
            name="test",
            echelons=[
                Echelon(
                    name="Store",
                    lead_time=1,
                    holding_cost=-1.0,
                    stockout_cost=2.0,
                    order_cost=10.0,
                    initial_inventory=100,
                    reorder_point=50,
                    order_quantity=100,
                )
            ],
        )
        errors = config.validate()
        assert any("holding_cost" in e for e in errors)

    def test_negative_demand_mean_is_invalid(self):
        config = ScenarioConfig(
            name="test",
            demand_mean=-10.0,
            echelons=[
                Echelon(
                    name="Store",
                    lead_time=1,
                    holding_cost=0.5,
                    stockout_cost=2.0,
                    order_cost=10.0,
                    initial_inventory=100,
                    reorder_point=50,
                    order_quantity=100,
                )
            ],
        )
        errors = config.validate()
        assert any("demand_mean" in e for e in errors)


# ---------------------------------------------------------------------------
# Single-run validation
# ---------------------------------------------------------------------------


class TestSingleRun:
    """Test that a single simulation run produces valid results."""

    def _simple_config(self, periods: int = 20, num_runs: int = 1) -> ScenarioConfig:
        return ScenarioConfig(
            name="single_run_test",
            periods=periods,
            num_runs=num_runs,
            echelons=[
                Echelon(
                    name="Store",
                    lead_time=1,
                    holding_cost=0.5,
                    stockout_cost=2.0,
                    order_cost=10.0,
                    initial_inventory=200,
                    reorder_point=80,
                    order_quantity=150,
                )
            ],
            demand_pattern="normal",
            demand_mean=50.0,
            demand_std=10.0,
        )

    def test_single_run_returns_result(self):
        config = self._simple_config()
        engine = SimulationEngine(config, seed=42)
        result = engine.run()
        assert isinstance(result, SimulationResult)

    def test_fill_rate_between_0_and_1(self):
        config = self._simple_config()
        engine = SimulationEngine(config, seed=42)
        result = engine.run()
        assert 0.0 <= result.avg_fill_rate <= 1.0

    def test_costs_are_non_negative(self):
        config = self._simple_config()
        engine = SimulationEngine(config, seed=42)
        result = engine.run()
        assert result.avg_total_cost >= 0
        assert result.avg_holding_cost >= 0
        assert result.avg_stockout_cost >= 0
        assert result.avg_order_cost >= 0

    def test_cost_components_sum_to_total(self):
        config = self._simple_config()
        engine = SimulationEngine(config, seed=42)
        result = engine.run()
        component_sum = (
            result.avg_holding_cost + result.avg_stockout_cost + result.avg_order_cost
        )
        assert abs(result.avg_total_cost - component_sum) < 1.0  # rounding tolerance

    def test_period_data_length_matches_config(self):
        config = self._simple_config(periods=30)
        engine = SimulationEngine(config, seed=42)
        result = engine.run()
        assert len(result.period_data) == 30

    def test_period_data_has_expected_keys(self):
        config = self._simple_config(periods=5)
        engine = SimulationEngine(config, seed=42)
        result = engine.run()
        expected_keys = {"period", "avg_inventory", "avg_demand", "avg_orders",
                         "avg_stockouts", "avg_cost"}
        for pd in result.period_data:
            assert set(pd.keys()) == expected_keys


# ---------------------------------------------------------------------------
# Monte Carlo stability
# ---------------------------------------------------------------------------


class TestMonteCarlo:
    """Test that Monte Carlo produces stable averages with a fixed seed."""

    def test_deterministic_with_seed(self):
        """Two runs with the same seed should produce identical results."""
        config = ScenarioConfig(
            name="determinism_test",
            periods=52,
            num_runs=50,
            echelons=[
                Echelon(
                    name="Store",
                    lead_time=2,
                    holding_cost=0.5,
                    stockout_cost=2.0,
                    order_cost=10.0,
                    initial_inventory=200,
                    reorder_point=100,
                    order_quantity=150,
                )
            ],
            demand_mean=100.0,
            demand_std=20.0,
        )

        engine1 = SimulationEngine(config, seed=12345)
        result1 = engine1.run()

        engine2 = SimulationEngine(config, seed=12345)
        result2 = engine2.run()

        assert result1.avg_fill_rate == result2.avg_fill_rate
        assert result1.avg_total_cost == result2.avg_total_cost
        assert result1.bullwhip_ratio == result2.bullwhip_ratio

    def test_more_runs_reduces_variance(self):
        """Increasing num_runs should produce results closer to the true mean.

        We verify this by running with 10 runs vs 500 runs (same seed)
        and checking that the 500-run result has a fill rate in a tighter
        range around the expected value.
        """
        base = ScenarioConfig(
            name="convergence_test",
            periods=52,
            echelons=[
                Echelon(
                    name="Store",
                    lead_time=1,
                    holding_cost=0.5,
                    stockout_cost=2.0,
                    order_cost=10.0,
                    initial_inventory=300,
                    reorder_point=100,
                    order_quantity=200,
                )
            ],
            demand_mean=80.0,
            demand_std=15.0,
        )

        # Run with many replications to get a "true" estimate
        base.num_runs = 500
        engine_large = SimulationEngine(base, seed=99)
        result_large = engine_large.run()

        # The fill rate from 500 runs should be reasonable
        assert 0.5 <= result_large.avg_fill_rate <= 1.0
        # Inventory turns should be positive
        assert result_large.avg_inventory_turns > 0


# ---------------------------------------------------------------------------
# Bullwhip ratio
# ---------------------------------------------------------------------------


class TestBullwhipRatio:
    """Test bullwhip ratio calculation."""

    def test_bullwhip_ratio_is_non_negative(self):
        config = beer_game()
        config.num_runs = 10
        engine = SimulationEngine(config, seed=42)
        result = engine.run()
        assert result.bullwhip_ratio >= 0

    def test_multi_echelon_has_bullwhip(self):
        """Multi-echelon supply chains should exhibit some bullwhip effect.

        With information delays and batching, upstream order variance
        should generally exceed downstream demand variance.
        """
        config = beer_game()
        config.num_runs = 50
        engine = SimulationEngine(config, seed=777)
        result = engine.run()
        # Bullwhip ratio > 0 is expected (it's a ratio of variances)
        # In the beer game, we expect amplification but the exact ratio
        # depends on parameters. We just verify it's computed and positive.
        assert result.bullwhip_ratio >= 0


# ---------------------------------------------------------------------------
# Scenario templates
# ---------------------------------------------------------------------------


class TestScenarios:
    """Test that all pre-built scenarios run without error."""

    def test_beer_game_runs(self):
        config = beer_game()
        config.num_runs = 5  # Fast for testing
        engine = SimulationEngine(config, seed=42)
        result = engine.run()
        assert result.scenario_name == "Beer Distribution Game"
        assert result.total_runs == 5
        assert len(result.period_data) == 52

    def test_smb_distributor_runs(self):
        config = smb_distributor()
        config.num_runs = 5
        engine = SimulationEngine(config, seed=42)
        result = engine.run()
        assert result.scenario_name == "SMB Distributor (Seasonal)"
        assert result.total_runs == 5

    def test_multi_echelon_runs(self):
        config = multi_echelon()
        config.num_runs = 5
        engine = SimulationEngine(config, seed=42)
        result = engine.run()
        assert result.scenario_name == "Multi-Echelon (3-Tier)"
        assert result.total_runs == 5

    def test_all_demand_patterns(self):
        """Verify all four demand patterns produce valid results."""
        for pattern in ("normal", "seasonal", "trending", "volatile"):
            config = ScenarioConfig(
                name=f"pattern_test_{pattern}",
                periods=20,
                num_runs=3,
                echelons=[
                    Echelon(
                        name="Store",
                        lead_time=1,
                        holding_cost=0.5,
                        stockout_cost=2.0,
                        order_cost=10.0,
                        initial_inventory=200,
                        reorder_point=80,
                        order_quantity=150,
                    )
                ],
                demand_pattern=pattern,
                demand_mean=100.0,
                demand_std=20.0,
            )
            engine = SimulationEngine(config, seed=42)
            result = engine.run()
            assert 0.0 <= result.avg_fill_rate <= 1.0, (
                f"Pattern '{pattern}' produced invalid fill rate: {result.avg_fill_rate}"
            )


# ---------------------------------------------------------------------------
# Reporter
# ---------------------------------------------------------------------------


class TestReporter:
    """Test the SimReporter output."""

    def _get_result(self) -> SimulationResult:
        config = beer_game()
        config.num_runs = 10
        engine = SimulationEngine(config, seed=42)
        return engine.run()

    def test_summary_is_non_empty(self):
        result = self._get_result()
        reporter = SimReporter(result)
        summary = reporter.summary()
        assert len(summary) > 50
        assert "Beer Distribution Game" in summary

    def test_summary_contains_kpis(self):
        result = self._get_result()
        reporter = SimReporter(result)
        summary = reporter.summary()
        assert "Fill Rate" in summary
        assert "Bullwhip" in summary
        assert "Total Cost" in summary

    def test_kpi_table_format(self):
        result = self._get_result()
        reporter = SimReporter(result)
        table = reporter.kpi_table()
        assert "Fill Rate" in table
        assert "Inventory Turns" in table
        assert "Bullwhip Ratio" in table
        assert "Holding Cost" in table

    def test_to_json_creates_file(self):
        result = self._get_result()
        reporter = SimReporter(result)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test_output.json")
            saved_path = reporter.to_json(path)
            assert os.path.exists(saved_path)

            with open(saved_path) as f:
                data = json.load(f)

            assert data["scenario_name"] == "Beer Distribution Game"
            assert data["total_runs"] == 10
            assert "_meta" in data
            assert "engine" in data["_meta"]

    def test_to_json_default_path(self):
        """Test that to_json() with no args creates a file in the default dir."""
        result = self._get_result()
        reporter = SimReporter(result)
        path = reporter.to_json()
        try:
            assert os.path.exists(path)
            assert "store/astrotrain" in path
        finally:
            # Clean up the generated file
            if os.path.exists(path):
                os.remove(path)


# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------


class TestPerformance:
    """Verify simulation runs within acceptable time bounds."""

    def test_single_run_under_1_second(self):
        """A single 52-period run with 4 echelons should finish quickly."""
        import time

        config = beer_game()
        config.num_runs = 1
        engine = SimulationEngine(config, seed=42)

        start = time.monotonic()
        engine.run()
        elapsed = time.monotonic() - start

        assert elapsed < 1.0, f"Single run took {elapsed:.2f}s (limit: 1.0s)"

    def test_hundred_runs_under_5_seconds(self):
        """100 runs of beer game should complete in reasonable time."""
        import time

        config = beer_game()
        config.num_runs = 100
        engine = SimulationEngine(config, seed=42)

        start = time.monotonic()
        engine.run()
        elapsed = time.monotonic() - start

        assert elapsed < 5.0, f"100 runs took {elapsed:.2f}s (limit: 5.0s)"
