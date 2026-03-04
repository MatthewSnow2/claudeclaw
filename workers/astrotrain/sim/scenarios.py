"""
Pre-built simulation scenario templates.

Each function returns a ScenarioConfig ready to pass to SimulationEngine.run().
These model well-known supply chain archetypes that are useful for
demonstrations, training, and baseline comparisons.
"""

from .engine import Echelon, ScenarioConfig


def beer_game() -> ScenarioConfig:
    """Classic MIT Beer Distribution Game.

    4-echelon supply chain: Retailer -> Wholesaler -> Distributor -> Factory.
    Demonstrates the bullwhip effect -- small demand perturbations at retail
    amplify into wild swings at the factory due to information delay and
    order batching.

    Assumptions:
        - Customer demand is normal(100, 15), fairly stable
        - Each echelon has 2-period lead time (information + shipping)
        - High stockout cost relative to holding to incentivize over-ordering
        - All echelons use the same (s, Q) policy with identical parameters
          to show how structural delays cause bullwhip even without
          irrational behavior
    """
    echelons = [
        Echelon(
            name="Retailer",
            lead_time=2,
            holding_cost=0.50,
            stockout_cost=2.00,
            order_cost=50.0,
            initial_inventory=200,
            reorder_point=150,
            order_quantity=200,
            review_period=1,
        ),
        Echelon(
            name="Wholesaler",
            lead_time=2,
            holding_cost=0.40,
            stockout_cost=1.50,
            order_cost=50.0,
            initial_inventory=200,
            reorder_point=150,
            order_quantity=200,
            review_period=1,
        ),
        Echelon(
            name="Distributor",
            lead_time=2,
            holding_cost=0.30,
            stockout_cost=1.00,
            order_cost=50.0,
            initial_inventory=200,
            reorder_point=150,
            order_quantity=250,
            review_period=1,
        ),
        Echelon(
            name="Factory",
            lead_time=3,
            holding_cost=0.20,
            stockout_cost=0.50,
            order_cost=100.0,
            initial_inventory=300,
            reorder_point=200,
            order_quantity=300,
            review_period=1,
        ),
    ]

    return ScenarioConfig(
        name="Beer Distribution Game",
        periods=52,
        num_runs=100,
        echelons=echelons,
        demand_pattern="normal",
        demand_mean=100.0,
        demand_std=15.0,
    )


def smb_distributor() -> ScenarioConfig:
    """Small-to-medium business distributor.

    Single-warehouse operation handling seasonal demand. Representative
    of a typical SMB that buys from manufacturers and sells to retailers
    or direct-to-consumer.

    Assumptions:
        - Seasonal demand (peak in Q4, trough in Q1) with mean 500 units/week
        - Single echelon (warehouse manages its own inventory)
        - 3-period lead time (typical for domestic freight)
        - Moderate holding cost, high stockout cost (lost sales = lost customers)
        - Periodic review every 2 periods (bi-weekly ordering cycle)
    """
    echelons = [
        Echelon(
            name="Warehouse",
            lead_time=3,
            holding_cost=0.25,
            stockout_cost=5.00,
            order_cost=75.0,
            initial_inventory=1500,
            reorder_point=800,
            order_quantity=1200,
            review_period=2,
        ),
    ]

    return ScenarioConfig(
        name="SMB Distributor (Seasonal)",
        periods=52,
        num_runs=100,
        echelons=echelons,
        demand_pattern="seasonal",
        demand_mean=500.0,
        demand_std=80.0,
    )


def multi_echelon() -> ScenarioConfig:
    """3-tier multi-echelon supply chain.

    Manufacturer -> Distributor -> Retailer. A general-purpose template
    for studying information sharing, lead time reduction, and inventory
    positioning across tiers.

    Assumptions:
        - Trending demand (growing market, +0.5%/period)
        - Manufacturer has longest lead time (production cycle)
        - Costs decrease upstream (cheaper to hold raw materials than
          finished goods near the customer)
        - Each tier has different review periods reflecting real-world
          ordering cadences
    """
    echelons = [
        Echelon(
            name="Retailer",
            lead_time=1,
            holding_cost=0.60,
            stockout_cost=3.00,
            order_cost=30.0,
            initial_inventory=300,
            reorder_point=200,
            order_quantity=250,
            review_period=1,
        ),
        Echelon(
            name="Distributor",
            lead_time=2,
            holding_cost=0.35,
            stockout_cost=1.50,
            order_cost=60.0,
            initial_inventory=500,
            reorder_point=350,
            order_quantity=400,
            review_period=2,
        ),
        Echelon(
            name="Manufacturer",
            lead_time=4,
            holding_cost=0.15,
            stockout_cost=0.75,
            order_cost=150.0,
            initial_inventory=800,
            reorder_point=500,
            order_quantity=600,
            review_period=4,
        ),
    ]

    return ScenarioConfig(
        name="Multi-Echelon (3-Tier)",
        periods=52,
        num_runs=100,
        echelons=echelons,
        demand_pattern="trending",
        demand_mean=200.0,
        demand_std=40.0,
    )
