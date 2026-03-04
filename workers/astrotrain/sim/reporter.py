"""
AstroTrain Simulation Reporter.

Transforms raw SimulationResult data into human-readable summaries,
formatted KPI tables, and JSON output for persistence and dashboards.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .engine import SimulationResult

# Default output directory for AstroTrain simulation results
DEFAULT_OUTPUT_DIR = "/home/apexaipc/projects/claudeclaw/store/astrotrain"


class SimReporter:
    """Reporting facade for simulation results.

    Takes a SimulationResult and produces executive summaries,
    KPI tables, and JSON exports.
    """

    def __init__(self, result: SimulationResult):
        self.result = result

    def summary(self) -> str:
        """Generate an executive summary of the simulation results.

        Returns a concise 5-10 line text block suitable for Telegram
        delivery or terminal output.
        """
        r = self.result
        lines = [
            f"SIMULATION RESULTS: {r.scenario_name}",
            f"Runs: {r.total_runs} | Periods: {len(r.period_data)}",
            "",
            f"Fill Rate: {r.avg_fill_rate:.1%} (95th pctl: {r.service_level_95:.1%})",
            f"Inventory Turns: {r.avg_inventory_turns:.1f} (annualized)",
            f"Bullwhip Ratio: {r.bullwhip_ratio:.2f}x",
            "",
            f"Total Cost: ${r.avg_total_cost:,.0f}",
            f"  Holding: ${r.avg_holding_cost:,.0f} | "
            f"Stockout: ${r.avg_stockout_cost:,.0f} | "
            f"Ordering: ${r.avg_order_cost:,.0f}",
        ]

        # Add interpretation
        if r.bullwhip_ratio > 2.0:
            lines.append("")
            lines.append(
                f"WARNING: Bullwhip ratio of {r.bullwhip_ratio:.2f}x indicates "
                "significant demand amplification upstream. "
                "Consider information sharing or VMI."
            )

        if r.avg_fill_rate < 0.90:
            lines.append("")
            lines.append(
                f"WARNING: Fill rate of {r.avg_fill_rate:.1%} is below 90%. "
                "Review safety stock levels and reorder points."
            )

        cost_breakdown = []
        total = r.avg_total_cost if r.avg_total_cost > 0 else 1
        if r.avg_holding_cost / total > 0.5:
            cost_breakdown.append("holding-heavy (excess inventory)")
        if r.avg_stockout_cost / total > 0.3:
            cost_breakdown.append("stockout-heavy (insufficient buffer)")
        if cost_breakdown:
            lines.append("")
            lines.append(f"Cost profile: {', '.join(cost_breakdown)}")

        return "\n".join(lines)

    def kpi_table(self) -> str:
        """Generate a formatted KPI table.

        Returns a fixed-width text table suitable for monospace rendering
        (terminal or Telegram code blocks).
        """
        r = self.result
        header = f"{'KPI':<30} {'Value':>15}"
        sep = "-" * 47

        rows = [
            ("Fill Rate (avg)", f"{r.avg_fill_rate:.2%}"),
            ("Fill Rate (95th pctl)", f"{r.service_level_95:.2%}"),
            ("Inventory Turns", f"{r.avg_inventory_turns:.1f}"),
            ("Bullwhip Ratio", f"{r.bullwhip_ratio:.2f}x"),
            ("", ""),
            ("Total Cost (avg)", f"${r.avg_total_cost:,.0f}"),
            ("  Holding Cost", f"${r.avg_holding_cost:,.0f}"),
            ("  Stockout Cost", f"${r.avg_stockout_cost:,.0f}"),
            ("  Ordering Cost", f"${r.avg_order_cost:,.0f}"),
            ("", ""),
            ("Simulation Runs", f"{r.total_runs}"),
            ("Periods", f"{len(r.period_data)}"),
        ]

        lines = [header, sep]
        for label, value in rows:
            if label == "":
                lines.append("")
            else:
                lines.append(f"{label:<30} {value:>15}")

        return "\n".join(lines)

    def to_json(self, path: str | None = None) -> str:
        """Save full simulation results as JSON.

        If path is not provided, generates a timestamped filename in
        the default output directory.

        Returns the absolute path of the saved file.
        """
        if path is None:
            os.makedirs(DEFAULT_OUTPUT_DIR, exist_ok=True)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            safe_name = self.result.scenario_name.lower().replace(" ", "_").replace("/", "_")
            filename = f"{safe_name}_{timestamp}.json"
            path = os.path.join(DEFAULT_OUTPUT_DIR, filename)
        else:
            # Ensure parent directory exists
            parent = Path(path).parent
            parent.mkdir(parents=True, exist_ok=True)

        data = asdict(self.result)
        data["_meta"] = {
            "engine": "AstroTrain Simulation Engine v1.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        with open(path, "w") as f:
            json.dump(data, f, indent=2)

        return os.path.abspath(path)
