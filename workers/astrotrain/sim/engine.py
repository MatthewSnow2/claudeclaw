"""
AstroTrain Simulation Engine.

Core Monte Carlo simulation for multi-echelon supply chain networks.
Models inventory dynamics, demand propagation, and cost accumulation
across configurable supply chain topologies.

Assumptions are stated explicitly. When uncertainty matters, we run
Monte Carlo. We don't pretend deterministic models capture reality.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass
class Echelon:
    """A single node in the supply chain network.

    Represents one tier (e.g., retailer, distributor, manufacturer).
    Each echelon maintains inventory, places orders upstream, and
    fulfills demand from downstream (or end customers).

    Attributes:
        name: Human-readable identifier for this tier.
        lead_time: Periods between placing and receiving an order.
        holding_cost: Cost per unit per period for inventory on hand.
        stockout_cost: Penalty per unit of unmet demand.
        order_cost: Fixed cost per order placed (regardless of quantity).
        initial_inventory: Starting inventory at period 0.
        reorder_point: Inventory level that triggers a new order.
        order_quantity: Quantity ordered when reorder point is breached.
        review_period: How often inventory is reviewed (1 = every period).
    """

    name: str
    lead_time: int
    holding_cost: float
    stockout_cost: float
    order_cost: float
    initial_inventory: int
    reorder_point: int
    order_quantity: int
    review_period: int = 1


@dataclass
class ScenarioConfig:
    """Configuration for a complete simulation scenario.

    Defines the supply chain topology, demand characteristics,
    and simulation parameters.

    Attributes:
        name: Scenario identifier.
        periods: Number of time periods to simulate (default 52 for weekly).
        num_runs: Number of Monte Carlo replications (default 100).
        echelons: List of supply chain tiers, ordered downstream to upstream
                  (index 0 = retailer/end, last = manufacturer/source).
        demand_pattern: Distribution shape for end-customer demand.
            - 'normal': stationary normal distribution
            - 'seasonal': sinusoidal pattern with noise
            - 'trending': linear trend with noise
            - 'volatile': heavy-tailed (lognormal-based) distribution
        demand_mean: Mean demand per period.
        demand_std: Standard deviation of demand per period.
    """

    name: str
    periods: int = 52
    num_runs: int = 100
    echelons: list[Echelon] = field(default_factory=list)
    demand_pattern: str = "normal"
    demand_mean: float = 100.0
    demand_std: float = 20.0

    def validate(self) -> list[str]:
        """Validate the scenario configuration. Returns list of errors (empty = valid)."""
        errors: list[str] = []
        if not self.name:
            errors.append("Scenario name is required.")
        if self.periods < 1:
            errors.append(f"Periods must be >= 1, got {self.periods}.")
        if self.num_runs < 1:
            errors.append(f"num_runs must be >= 1, got {self.num_runs}.")
        if not self.echelons:
            errors.append("At least one echelon is required.")
        if self.demand_pattern not in ("normal", "seasonal", "trending", "volatile"):
            errors.append(
                f"Unknown demand_pattern '{self.demand_pattern}'. "
                "Valid: normal, seasonal, trending, volatile."
            )
        if self.demand_mean <= 0:
            errors.append(f"demand_mean must be > 0, got {self.demand_mean}.")
        if self.demand_std < 0:
            errors.append(f"demand_std must be >= 0, got {self.demand_std}.")
        for i, ech in enumerate(self.echelons):
            if ech.lead_time < 0:
                errors.append(f"Echelon {i} ({ech.name}): lead_time must be >= 0.")
            if ech.holding_cost < 0:
                errors.append(f"Echelon {i} ({ech.name}): holding_cost must be >= 0.")
            if ech.stockout_cost < 0:
                errors.append(f"Echelon {i} ({ech.name}): stockout_cost must be >= 0.")
            if ech.order_cost < 0:
                errors.append(f"Echelon {i} ({ech.name}): order_cost must be >= 0.")
            if ech.review_period < 1:
                errors.append(f"Echelon {i} ({ech.name}): review_period must be >= 1.")
        return errors


@dataclass
class SimulationResult:
    """Aggregated results from a Monte Carlo simulation.

    All 'avg_' fields are means across all runs. service_level_95 is
    the 95th percentile of per-run service levels (i.e., 95% of runs
    achieved at least this service level).

    Attributes:
        scenario_name: Name of the scenario that produced these results.
        total_runs: Number of Monte Carlo replications completed.
        avg_fill_rate: Mean fraction of demand fulfilled on time (0-1).
        avg_inventory_turns: Mean annualized inventory turnover ratio.
        avg_total_cost: Mean total cost across all echelons and periods.
        avg_holding_cost: Mean holding cost component.
        avg_stockout_cost: Mean stockout cost component.
        avg_order_cost: Mean ordering cost component.
        service_level_95: 5th percentile of per-run fill rates (the level
            achieved in 95% of runs).
        bullwhip_ratio: Ratio of upstream order variance to downstream
            demand variance. Values > 1 indicate demand amplification.
        period_data: Per-period averages across runs, each dict contains
            'period', 'avg_inventory', 'avg_demand', 'avg_orders',
            'avg_stockouts', 'avg_cost'.
    """

    scenario_name: str
    total_runs: int
    avg_fill_rate: float
    avg_inventory_turns: float
    avg_total_cost: float
    avg_holding_cost: float
    avg_stockout_cost: float
    avg_order_cost: float
    service_level_95: float
    bullwhip_ratio: float
    period_data: list[dict] = field(default_factory=list)


class SimulationEngine:
    """Monte Carlo supply chain simulation engine.

    Generates stochastic demand, propagates orders through a multi-echelon
    network, and tracks inventory/cost KPIs across many replications.

    Assumptions (stated explicitly per AstroTrain rules):
        1. Demand is exogenous and only hits echelon 0 (the retailer).
        2. Upstream echelons see demand as the orders placed by their
           immediate downstream neighbor.
        3. The most upstream echelon has unlimited raw material supply
           (infinite capacity assumption).
        4. Lead times are deterministic (no supply variability).
        5. Backorders are allowed (unmet demand is lost, not backlogged).
        6. Review policy is periodic review with (s, Q) -- reorder point
           and fixed order quantity.
        7. All costs are linear (no economies of scale in holding/ordering).
    """

    def __init__(self, config: ScenarioConfig, seed: Optional[int] = None):
        errors = config.validate()
        if errors:
            raise ValueError(
                "Invalid scenario configuration:\n" + "\n".join(f"  - {e}" for e in errors)
            )
        self.config = config
        self.seed = seed
        self._rng = np.random.default_rng(seed)

    def _generate_demand(self, periods: int) -> np.ndarray:
        """Generate a demand time series based on the configured pattern.

        Returns an array of non-negative demand values with length `periods`.
        """
        mean = self.config.demand_mean
        std = self.config.demand_std
        pattern = self.config.demand_pattern

        if pattern == "normal":
            demand = self._rng.normal(mean, std, periods)

        elif pattern == "seasonal":
            # Sinusoidal seasonal pattern: one full cycle per 52 periods
            t = np.arange(periods)
            seasonal_component = mean * 0.3 * np.sin(2 * np.pi * t / 52)
            noise = self._rng.normal(0, std * 0.5, periods)
            demand = mean + seasonal_component + noise

        elif pattern == "trending":
            # Linear upward trend: +0.5% of mean per period
            t = np.arange(periods)
            trend = mean * 0.005 * t
            noise = self._rng.normal(0, std, periods)
            demand = mean + trend + noise

        elif pattern == "volatile":
            # Lognormal-based heavy tails
            # Parameterize lognormal to match desired mean and std
            sigma_ln = math.sqrt(math.log(1 + (std / mean) ** 2))
            mu_ln = math.log(mean) - 0.5 * sigma_ln**2
            demand = self._rng.lognormal(mu_ln, sigma_ln, periods)

        else:
            raise ValueError(f"Unknown demand pattern: {pattern}")

        # Demand cannot be negative; floor at 0 and round to integers
        return np.maximum(demand, 0).round().astype(int)

    def _run_single(self) -> dict:
        """Execute a single simulation run.

        Returns a dict with per-echelon and per-period metrics.
        """
        periods = self.config.periods
        echelons = self.config.echelons
        n_ech = len(echelons)

        # Generate end-customer demand
        customer_demand = self._generate_demand(periods)

        # State arrays: inventory[echelon][period], orders[echelon][period]
        inventory = np.zeros((n_ech, periods), dtype=float)
        orders_placed = np.zeros((n_ech, periods), dtype=float)
        demand_seen = np.zeros((n_ech, periods), dtype=float)
        stockouts = np.zeros((n_ech, periods), dtype=float)
        fulfilled = np.zeros((n_ech, periods), dtype=float)

        # Pipeline: orders in transit. pipeline[echelon] = list of (arrival_period, qty)
        pipelines: list[list[tuple[int, int]]] = [[] for _ in range(n_ech)]

        # Initialize inventory
        for e in range(n_ech):
            if periods > 0:
                inventory[e, 0] = echelons[e].initial_inventory

        # Cost accumulators
        total_holding = 0.0
        total_stockout = 0.0
        total_order = 0.0

        for t in range(periods):
            # --- Phase 1: Receive incoming shipments ---
            for e in range(n_ech):
                arrived = 0
                remaining = []
                for arrival_period, qty in pipelines[e]:
                    if arrival_period <= t:
                        arrived += qty
                    else:
                        remaining.append((arrival_period, qty))
                pipelines[e] = remaining
                inventory[e, t] += arrived

            # --- Phase 2: Fulfill demand ---
            for e in range(n_ech):
                if e == 0:
                    # Retailer faces customer demand
                    demand = customer_demand[t]
                else:
                    # Upstream echelons face orders from downstream
                    demand = int(orders_placed[e - 1, t - 1]) if t > 0 else 0

                demand_seen[e, t] = demand
                available = inventory[e, t]
                fill = min(available, demand)
                fulfilled[e, t] = fill
                shortage = max(0, demand - available)
                stockouts[e, t] = shortage
                inventory[e, t] -= fill

            # --- Phase 3: Place orders (periodic review) ---
            for e in range(n_ech):
                ech_cfg = echelons[e]
                if t % ech_cfg.review_period == 0:
                    if inventory[e, t] <= ech_cfg.reorder_point:
                        order_qty = ech_cfg.order_quantity
                        orders_placed[e, t] = order_qty
                        # Order arrives after lead_time periods
                        arrival = t + ech_cfg.lead_time
                        if e < n_ech - 1:
                            # Non-terminal echelon: order goes to upstream echelon
                            # (will be fulfilled in the upstream's demand phase)
                            pipelines[e].append((arrival, order_qty))
                        else:
                            # Most upstream: infinite supply assumption
                            pipelines[e].append((arrival, order_qty))

            # --- Phase 4: Accumulate costs ---
            for e in range(n_ech):
                ech_cfg = echelons[e]
                on_hand = max(0, inventory[e, t])
                total_holding += on_hand * ech_cfg.holding_cost
                total_stockout += stockouts[e, t] * ech_cfg.stockout_cost
                if orders_placed[e, t] > 0:
                    total_order += ech_cfg.order_cost

            # --- Phase 5: Carry inventory to next period ---
            if t + 1 < periods:
                for e in range(n_ech):
                    inventory[e, t + 1] = inventory[e, t]

        # --- Compute run-level KPIs ---
        total_demand = customer_demand.sum()
        total_fulfilled = fulfilled[0].sum()
        fill_rate = total_fulfilled / total_demand if total_demand > 0 else 1.0

        # Inventory turns: annualized COGS / avg inventory
        # Using demand as proxy for COGS, and average on-hand across all echelons
        avg_inventory = np.maximum(inventory, 0).mean()
        avg_demand_per_period = customer_demand.mean()
        inv_turns = (avg_demand_per_period * 52) / avg_inventory if avg_inventory > 0 else 0.0

        # Bullwhip ratio: var(upstream orders) / var(customer demand)
        # Use the most upstream echelon's orders vs customer demand
        upstream_orders = orders_placed[-1]
        var_demand = np.var(customer_demand) if np.var(customer_demand) > 0 else 1.0
        var_upstream = np.var(upstream_orders)
        bullwhip = var_upstream / var_demand

        # Period-level data
        period_records = []
        for t in range(periods):
            period_records.append(
                {
                    "period": t,
                    "total_inventory": float(np.maximum(inventory[:, t], 0).sum()),
                    "customer_demand": float(customer_demand[t]),
                    "total_orders": float(orders_placed[:, t].sum()),
                    "total_stockouts": float(stockouts[:, t].sum()),
                    "total_cost": float(
                        sum(
                            max(0, inventory[e, t]) * echelons[e].holding_cost
                            + stockouts[e, t] * echelons[e].stockout_cost
                            + (echelons[e].order_cost if orders_placed[e, t] > 0 else 0)
                            for e in range(n_ech)
                        )
                    ),
                }
            )

        return {
            "fill_rate": fill_rate,
            "inv_turns": inv_turns,
            "total_cost": total_holding + total_stockout + total_order,
            "holding_cost": total_holding,
            "stockout_cost": total_stockout,
            "order_cost": total_order,
            "bullwhip": bullwhip,
            "period_data": period_records,
        }

    def run(self) -> SimulationResult:
        """Execute the full Monte Carlo simulation.

        Runs num_runs independent replications with different demand
        realizations. Aggregates results into a SimulationResult.
        """
        n = self.config.num_runs
        fill_rates = []
        inv_turns_list = []
        total_costs = []
        holding_costs = []
        stockout_costs = []
        order_costs = []
        bullwhips = []

        # For period-level averaging
        periods = self.config.periods
        agg_inventory = np.zeros(periods)
        agg_demand = np.zeros(periods)
        agg_orders = np.zeros(periods)
        agg_stockouts = np.zeros(periods)
        agg_cost = np.zeros(periods)

        for _ in range(n):
            result = self._run_single()
            fill_rates.append(result["fill_rate"])
            inv_turns_list.append(result["inv_turns"])
            total_costs.append(result["total_cost"])
            holding_costs.append(result["holding_cost"])
            stockout_costs.append(result["stockout_cost"])
            order_costs.append(result["order_cost"])
            bullwhips.append(result["bullwhip"])

            for pd in result["period_data"]:
                t = pd["period"]
                agg_inventory[t] += pd["total_inventory"]
                agg_demand[t] += pd["customer_demand"]
                agg_orders[t] += pd["total_orders"]
                agg_stockouts[t] += pd["total_stockouts"]
                agg_cost[t] += pd["total_cost"]

        # Average period data
        period_data = []
        for t in range(periods):
            period_data.append(
                {
                    "period": t,
                    "avg_inventory": round(agg_inventory[t] / n, 2),
                    "avg_demand": round(agg_demand[t] / n, 2),
                    "avg_orders": round(agg_orders[t] / n, 2),
                    "avg_stockouts": round(agg_stockouts[t] / n, 2),
                    "avg_cost": round(agg_cost[t] / n, 2),
                }
            )

        # 95th percentile service level: 5th percentile of fill rates
        # (meaning 95% of runs had at least this fill rate)
        service_95 = float(np.percentile(fill_rates, 5))

        return SimulationResult(
            scenario_name=self.config.name,
            total_runs=n,
            avg_fill_rate=round(float(np.mean(fill_rates)), 4),
            avg_inventory_turns=round(float(np.mean(inv_turns_list)), 2),
            avg_total_cost=round(float(np.mean(total_costs)), 2),
            avg_holding_cost=round(float(np.mean(holding_costs)), 2),
            avg_stockout_cost=round(float(np.mean(stockout_costs)), 2),
            avg_order_cost=round(float(np.mean(order_costs)), 2),
            service_level_95=round(service_95, 4),
            bullwhip_ratio=round(float(np.mean(bullwhips)), 4),
            period_data=period_data,
        )
