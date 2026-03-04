# Agentic SCM: Comprehensive Review & Strategic Analysis

**Date:** 2026-02-28
**Author:** Soundwave (Research Agent)
**Status:** Complete
**Audience:** Matthew Snow / M2AI -- for Skool AI community pitch refinement

---

## Executive Summary

The supply chain management software market ($36.4B in 2026, 14.6% CAGR) is undergoing a generational shift from reactive, batch-forecast systems to autonomous, agent-driven orchestration. The agentic AI market alone hits ~$10B in 2026 with a 42% CAGR. Harvard Business Review published "When Supply Chains Become Autonomous" in Dec 2025, signaling mainstream validation.

M2AI has a credible head start: a working simulation engine (mcp-dsp-game) with 7 reusable architectural patterns, a production-quality pitch deck, and a clear beachhead thesis. The gap is between "game demo" and "real-world pilot." This report maps that gap and recommends how to close it.

---

## 1. SCM Simulation Landscape

### 1.1 Enterprise Platforms (>$100K/yr)

| Platform | Type | Strengths | Weaknesses | Price Range |
|----------|------|-----------|------------|-------------|
| **AnyLogic** | Multi-method (DES + ABM + SD) | Most flexible modeling; Java-based extensibility; 3D viz | Steep learning curve; expensive; requires simulation expertise | $50K-$200K+/yr |
| **FlexSim** | 3D DES | Strong 3D visualization; drag-and-drop; healthcare/logistics focus | Less agent-based capability; Windows-only | $25K-$150K+/yr |
| **Simio** | Object-oriented DES + scheduling | Combines simulation with production scheduling; good for manufacturing | Smaller ecosystem; less agent-based modeling | $30K-$100K+/yr |
| **Arena (Rockwell)** | Classic DES | Industry standard; huge install base; well-documented | Dated UI; limited AI integration; Windows-only | $25K-$75K+/yr |

### 1.2 Enterprise SCM Planning Platforms

| Platform | Focus | Mid-Market Fit | Notes |
|----------|-------|----------------|-------|
| **Kinaxis RapidResponse** | Concurrent planning | Medium (complexity barrier) | Strong "what-if" scenarios; 18-24mo implementation |
| **o9 Solutions** | AI-powered IBP | Low (enterprise pricing) | Digital brain concept; raised $295M+ |
| **Blue Yonder** | End-to-end SCM | Low (18-24mo implementation) | Panasonic-owned; full suite |
| **Coupa** | Procurement + supply chain | Medium | Acquired by Thoma Bravo for $8B |

**Key insight:** These platforms serve Fortune 500. Implementation timelines of 18-24 months and 6-figure annual costs lock out mid-market distributors entirely.

### 1.3 Open-Source Frameworks

| Framework | Language | Type | SCM Applicability |
|-----------|----------|------|-------------------|
| **Mesa** | Python | Agent-based modeling | High -- model suppliers, distributors, retailers as autonomous agents |
| **SimPy** | Python | Discrete event simulation | High -- model order flows, warehouse operations, transport |
| **AgentPy** | Python | Agent-based modeling | Medium -- lighter than Mesa, good for prototyping |
| **HASH** | TypeScript | Agent-based simulation | Medium -- browser-native, visual but less mature |

**Assessment:** Mesa + SimPy is the natural foundation for an agentic SCM simulation built in Python. Both are Apache2 licensed. Mesa had a major 3.0 release in 2025 with improved modularity.

### 1.4 Beer Game / Educational Simulations

| Platform | Model | Use |
|----------|-------|-----|
| **MIT Sloan Beer Game** | 4-tier linear chain | Academic teaching (bullwhip effect) |
| **Zensimu** | Customizable multi-tier | Corporate training + consulting |
| **transentis Beergame** | Classic + variants | Online multiplayer |

**Relevance:** The beer distribution game is the canonical SCM simulation. DSP game mechanics map directly to it (see Section 4). The beer game's 4-tier structure (Retailer -> Wholesaler -> Distributor -> Factory) is the exact topology M2AI's agentic system should target.

---

## 2. The Agentic SCM Opportunity

### 2.1 Why Now

Three converging forces:

1. **LLM capability jump** -- Claude, GPT-4, Gemini can now reason about multi-variable tradeoffs, read unstructured supplier emails, and generate purchase orders. This was impossible 2 years ago.

2. **Supply chain trauma** -- COVID, Suez Canal, semiconductor shortages. Boards now treat supply chain as strategic, not back-office. McKinsey data: AI in distribution trims inventory 20-30% and cuts logistics costs 5-20%.

3. **Mid-market underserved** -- Enterprise platforms require $500K+ and 18-month implementations. Mid-market distributors ($50M-$500M revenue) run on spreadsheets, email, and gut feel. They have the pain but not the budget for traditional solutions.

### 2.2 Where Agents Beat Traditional Optimization

| Capability | Traditional (LP/MIP solvers) | Agentic (LLM-based) |
|------------|------------------------------|----------------------|
| **Demand sensing** | Historical time series | Real-time signal fusion (POS, weather, social, supplier status) |
| **Exception handling** | Pre-coded rules | Reason about novel situations; natural language escalation |
| **Supplier negotiation** | Static contracts | Dynamic negotiation based on context |
| **Cross-functional coordination** | Siloed modules | Multi-agent collaboration (procurement talks to logistics) |
| **Explanation** | Opaque solver output | Natural language rationale for every decision |
| **Setup time** | 6-18 months configuration | Days to weeks (prompt-driven) |
| **Adaptability** | Re-model and re-solve | Continuous learning from outcomes |

### 2.3 Where Agents Are Weak (Be Honest)

- **Deterministic optimization**: LP/MIP solvers will always beat LLMs at pure math optimization (bin packing, vehicle routing, lot sizing)
- **High-frequency decisions**: Sub-second inventory allocation is still solver territory
- **Regulatory compliance**: Hard constraints (FIFO, lot traceability) need deterministic enforcement, not probabilistic reasoning
- **Cost at scale**: LLM inference per decision is expensive vs. a solver that runs once

**Strategic implication:** The winning architecture is **agents for reasoning + solvers for optimization**. Agents decide *what* to optimize; solvers execute the math. This is the hybrid moat.

### 2.4 Industry Validation

- **HBR Dec 2025**: "When Supply Chains Become Autonomous" -- mainstream recognition
- **EY**: "Revolutionizing Global Supply Chains with Agentic AI" -- consulting firms now selling this
- **IBM + Oracle**: Joint report on agentic AI for supply chain resilience
- **WEF Nov 2025**: "Autonomous Orchestration -- Next Frontier of Supply Chain Management"
- **Prolifics, Kanerika, Dataiku, ICRON**: All publishing 2026 agentic SCM guides

The thesis is validated. The question is no longer "will this happen?" but "who gets there first with a product that works?"

---

## 3. mcp-dsp-game: Reusable Patterns

### 3.1 Architecture Overview

The mcp-dsp-game is a 3-layer MCP server that enables Claude to analyze Dyson Sphere Program factory optimization:

```
Layer 3: Claude (AI Client)
    |  MCP Protocol (stdio/SSE)
Layer 2: Python MCP Server (FastMCP 3.0.2)
    |  WebSocket (ws://localhost:8470)
Layer 1: C# BepInEx Plugin (Unity Runtime)
    |  Harmony IL Patches
Layer 0: Dyson Sphere Program (Unity Game)
```

**Stats:** 8 MCP tools, 101 tests at 88% coverage, 53 recipes in dependency graph, Pydantic 2.12 data models.

### 3.2 Seven Transferable Patterns

#### Pattern 1: Hierarchical State Model
```
FactoryState -> planets -> production/assemblers/belts/power
```
**Maps to:** `SupplyChainState -> facilities -> SKUs/lines/transport/capacity`

This is the most directly reusable pattern. Multi-level aggregation from item-level to facility-level to network-level. The Pydantic model hierarchy is clean and extensible.

#### Pattern 2: Data Source Router (Intelligent Fallback)
Real-time WebSocket vs. save file parsing with automatic failover, health checks, and latency tracking.

**Maps to:** Real-time API feeds vs. batch ERP exports. Real-world SCM data is messy -- you need graceful degradation when a supplier API goes down. This pattern handles it.

#### Pattern 3: Dependency Graph Traversal (BOM Explosion)
`build_dependency_graph()` and `trace_bottleneck_upstream()` traverse recipe trees to find root causes.

**Maps to:** Bill of Materials (BOM) explosion is identical. "Why is Product X late?" -> trace upstream through components -> subcomponents -> raw materials -> suppliers. This is the core analytical operation in SCM.

#### Pattern 4: Bottleneck Detection Algorithm
Groups assemblers by recipe, calculates efficiency, detects starvation/blocking, ranks by severity, provides recommendations.

**Maps to:** Production line efficiency monitoring. The algorithm (>30% starved = input bottleneck, <80% efficiency = constraint) translates directly. Swap "assembler" for "production line" or "warehouse."

#### Pattern 5: Event-Driven Metrics Accumulation
Thread-safe C# accumulator pattern: events fire on production/power/belt activity, periodic snapshot rollup.

**Maps to:** Supply chain event stream processing. Order events, shipment events, inventory adjustments all use this pattern. Accumulate, snapshot, analyze.

#### Pattern 6: Configuration-Driven Analysis Thresholds
Parameterized: saturation_threshold=95%, efficiency_floor=80%, bottleneck_severity=50.

**Maps to:** Configurable alerting per customer. Different distributors have different tolerances. Same engine, different config.

#### Pattern 7: MCP Tool Interface for AI Reasoning
FastMCP tools with structured inputs/outputs that Claude can invoke through natural language.

**Maps to:** This is the agent interface. The MCP pattern means any LLM can drive the simulation through tool calls. This is the agentic SCM control plane.

### 3.3 What's NOT Reusable

- C# BepInEx plugin (game-specific)
- DSP save file parser (game-specific binary format)
- Recipe database content (DSP items, not real products)
- 3D visualization (DSP renders it; real product needs its own)

### 3.4 Reuse Estimate

~40% of the Python codebase is directly transferable:
- `models/factory_state.py` -> `models/supply_chain_state.py` (rename + extend)
- `data_sources/router.py` -> reuse as-is with new connectors
- `tools/bottleneck_analyzer.py` -> adapt thresholds for real metrics
- `utils/recipe_database.py` -> `bom_database.py` (structure identical)
- `tools/logistics_analyzer.py` -> adapt belt tiers to transport modes
- Test patterns (mock WebSocket, integration harness) -> reuse directly

---

## 4. DSP to Real-World SCM Mapping

### 4.1 Concept Mapping

| DSP Game Concept | Real-World SCM Equivalent | Complexity Delta |
|------------------|---------------------------|------------------|
| Planet | Facility (warehouse, factory, DC) | Same -- geographic node |
| Assembler | Production line / processing station | Same -- transforms inputs to outputs |
| Recipe | Bill of Materials (BOM) | Same structure, more depth in real world |
| Belt (conveyor) | Transport lane (truck, rail, ship) | Higher -- variable transit time, cost, capacity |
| Belt throughput | Lane capacity (units/day) | Same metric, different units |
| Belt saturation | Lane utilization % | Same concept |
| Power grid | Capacity constraint (labor, equipment, budget) | Broader -- power is one of many constraints |
| Iron ore -> Iron ingot | Raw material -> Component | Same dependency chain |
| Input starvation | Stockout / supply shortage | Same signal |
| Output blocked | Excess inventory / demand shortfall | Same signal |
| Game tick | Time period (hour, day, week) | Same -- configurable granularity |
| Recipe dependency graph | BOM explosion tree | Identical algorithm |
| Production rate (items/min) | Throughput (units/period) | Same metric |
| Efficiency % | OEE (Overall Equipment Effectiveness) | Same formula, more dimensions |

### 4.2 What DSP Simplifies (Gaps to Fill)

| DSP Assumption | Real-World Reality | Engineering Cost |
|----------------|-------------------|------------------|
| Deterministic demand | Stochastic demand with seasonality, trends, events | High -- need forecasting agent |
| Instant transport (belts) | Variable lead times (days to weeks) | Medium -- add transit time model |
| No cost model | Multi-currency cost optimization | Medium -- add cost layer |
| No suppliers (ores are free) | Supplier selection, negotiation, reliability | High -- need procurement agent |
| Single player | Multi-stakeholder (buyers, suppliers, logistics) | High -- multi-party coordination |
| Perfect information | Incomplete, delayed, sometimes wrong data | Medium -- data quality layer |
| No disruptions | Disruptions are the whole point | Medium -- disruption event model |

### 4.3 The Bridge Architecture

```
DSP Demo (Phase 1)           Real-World MVP (Phase 3)
=================            =======================
MCP Server (FastMCP)    ->   MCP Server (FastMCP)  [REUSE]
FactoryState model      ->   SupplyChainState      [EXTEND]
Recipe DB               ->   BOM Database           [REPLACE DATA]
Bottleneck Analyzer     ->   Bottleneck Analyzer    [RETUNE]
Logistics Analyzer      ->   Transport Optimizer    [EXTEND]
Power Analyzer          ->   Capacity Planner       [GENERALIZE]
WebSocket data source   ->   ERP/WMS API connector  [REPLACE]
Save file parser        ->   CSV/Excel importer     [REPLACE]

NEW COMPONENTS:
                             Demand Forecast Agent
                             Procurement Agent
                             Rebalance Agent
                             Cost Optimizer (LP solver)
                             Disruption Event Engine
                             Dashboard (Next.js)
```

---

## 5. Beachhead Use Case

### 5.1 Candidate Evaluation

| Segment | Pain Intensity | Willingness to Pay | Accessibility | Technical Fit | Score |
|---------|---------------|--------------------|--------------|--------------|----|
| Mid-tier enterprise ($50M-$500M) | High | High ($50K-$200K/yr) | Medium (procurement cycles) | High | 8/10 |
| SMB wholesale distributors | Very High | Medium ($5K-$30K/yr) | High (owner-decides) | High | 9/10 |
| 3PL/logistics providers | High | High | Medium | Medium | 7/10 |
| CPG manufacturers | Very High | Very High | Low (enterprise procurement) | High | 6/10 |
| Owner-operator services | Medium | Low ($1K-$5K/yr) | Very High | Low | 4/10 |

### 5.2 Recommended Beachhead: SMB Wholesale Distributors

**Who:** Regional wholesalers and distributors with $10M-$100M revenue, 1-5 warehouses, 500-5000 SKUs, 5-50 employees in operations.

**Why this segment:**

1. **Acute pain, low tech maturity.** They run on spreadsheets, QuickBooks, and phone calls. They over-order to avoid stockouts, carry 30-60 days excess inventory, and manually track reorder points. McKinsey says AI can cut their inventory 20-30% -- that's real cash back.

2. **Decision maker = owner.** No procurement committee, no 12-month RFP cycle. The owner feels the inventory pain daily and can make a buying decision in one meeting.

3. **Technical simplicity.** Small product catalogs (hundreds, not millions of SKUs), simple supply chains (1-3 tiers), clear data sources (QuickBooks, Shopify, Excel). This is tractable for an MVP.

4. **Clear value metric.** "We freed up $X in working capital by reducing your inventory from 45 days to 25 days while maintaining 98% fill rate." Quantifiable ROI they understand.

5. **Land and expand.** Start with inventory optimization, expand to automated purchasing, then demand forecasting, then supplier management. Each module is a revenue expansion.

### 5.3 Anti-Beachhead (What to Avoid)

- **Fortune 500**: Long sales cycles, existing vendor lock-in, security reviews
- **Regulated industries** (pharma, food safety): Compliance overhead before you prove the core value
- **Pure services businesses**: No inventory to optimize

### 5.4 Job-to-Be-Done

"Help me stop running out of my best sellers while sitting on dead stock I can't move. I don't have time to stare at spreadsheets -- just tell me what to buy, when, and how much."

---

## 6. Competitive Positioning

### 6.1 Landscape Map

```
                    High Complexity
                         |
    Blue Yonder    Kinaxis    o9 Solutions
    (Full suite)   (Planning) (AI-native)
                         |
         Enterprise -----|---------- Mid-Market
                         |
    Coupa          NetSuite     Fishbowl
    (Procurement)  (ERP+SCM)   (Inventory)
                         |
                    Low Complexity

    WHERE M2AI PLAYS:

                    "Agentic Intelligence"
                         |
                    [M2AI: Agentic SCM]
                    Mid-market + AI-first
                    Agent-driven, not module-driven
```

### 6.2 Differentiation

| Dimension | Traditional SCM Software | M2AI Agentic SCM |
|-----------|------------------------|-------------------|
| Setup | 6-18 months | Days (connect ERP, configure agents) |
| Intelligence | Rules + historical models | LLM reasoning + real-time signals |
| Interface | Dashboards + reports | Natural language + autonomous actions |
| Decision making | Human reviews dashboard, decides | Agent recommends, human approves (graduating to auto) |
| Cost | $50K-$500K/yr | $5K-$30K/yr (SaaS) |
| Adaptability | Re-configure modules | Agents learn from outcomes |

### 6.3 Moat Strategy

1. **Data flywheel**: Every decision outcome trains better agents (with permission)
2. **Multi-agent coordination IP**: The orchestration patterns between forecast/procurement/rebalance agents
3. **Simulation-first development**: The DSP game proves the architecture before real money is at stake
4. **Speed to value**: Days, not months. This is the mid-market killer feature.

---

## 7. Technical Approach

### 7.1 Proposed Architecture

```
                    +------------------+
                    |   Dashboard UI   |
                    |   (Next.js 15)   |
                    +--------+---------+
                             |
                    +--------+---------+
                    |   API Gateway    |
                    |   (FastAPI)      |
                    +--------+---------+
                             |
              +--------------+--------------+
              |              |              |
     +--------+--+   +------+----+   +-----+------+
     | Signal    |   | Forecast  |   | Procurement|
     | Agent     |   | Agent     |   | Agent      |
     | (Ingest,  |   | (Demand   |   | (PO gen,   |
     |  normalize|   |  predict) |   |  vendor    |
     |  anomaly) |   |           |   |  select)   |
     +-----------+   +-----------+   +-----+------+
              |              |              |
              +--------------+--------------+
                             |
                    +--------+---------+
                    | Rebalance Agent  |
                    | (Inventory opt,  |
                    |  inter-facility) |
                    +--------+---------+
                             |
              +--------------+--------------+
              |              |              |
     +--------+--+   +------+----+   +-----+------+
     | Simulation|   | BOM/Recipe|   | Data       |
     | Engine    |   | Database  |   | Connectors |
     | (Mesa +   |   | (from DSP |   | (ERP, WMS, |
     |  SimPy)   |   |  pattern) |   |  CSV, API) |
     +-----------+   +-----------+   +------------+
```

### 7.2 Tech Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| Agents | Claude API (Sonnet for reasoning, Haiku for routing) | Best tool-use capability; M2AI expertise |
| Simulation | Mesa 3 + SimPy | Open-source, Python-native, agent-based + discrete event |
| API | FastAPI + Pydantic 2 | Existing M2AI stack; async; typed |
| Data | SQLite (local-first) -> PostgreSQL (multi-tenant) | Match existing pattern; scale when needed |
| Frontend | Next.js 15 + Shadcn/ui | Existing M2AI stack |
| Optimization | OR-Tools (Google) or PuLP | Open-source LP/MIP for deterministic optimization |
| MCP | FastMCP 3 | Already proven in DSP game; agent control plane |

### 7.3 Data Connectors (MVP)

Priority order:
1. **CSV/Excel upload** -- every distributor can export from QuickBooks
2. **QuickBooks API** -- dominant SMB accounting platform
3. **Shopify API** -- e-commerce demand signal
4. **Manual entry** -- fallback for smallest customers

Phase 2 connectors: NetSuite, SAP Business One, Fishbowl, Dear Inventory.

### 7.4 Simulation Engine Design

The simulation should model a multi-tier supply chain with these entities:

```python
# Core entities (adapted from DSP FactoryState pattern)
class Facility:         # Warehouse, DC, factory
    inventory: Dict[SKU, InventoryPosition]
    capacity: CapacityConstraints
    location: GeoCoord

class SKU:              # Product
    bom: Optional[BOM]  # If manufactured
    demand_profile: DemandProfile
    reorder_policy: ReorderPolicy

class TransportLane:    # Replaces DSP "Belt"
    origin: Facility
    destination: Facility
    capacity: float     # units/day
    lead_time: Duration
    cost_per_unit: float
    utilization: float  # 0-100%

class Supplier:         # NEW (not in DSP)
    items: List[SKU]
    lead_time: Duration
    reliability: float  # 0-100%
    moq: float          # Minimum order quantity
    pricing: PricingTier

class PurchaseOrder:    # NEW
    supplier: Supplier
    items: List[OrderLine]
    status: POStatus
    expected_delivery: datetime
```

### 7.5 Agent Definitions

| Agent | Model | Triggers | Actions | Guardrails |
|-------|-------|----------|---------|------------|
| Signal Agent | Haiku | New data ingestion | Normalize, detect anomalies, flag alerts | Read-only; no state changes |
| Forecast Agent | Sonnet | Daily/weekly cycle | Generate demand forecasts per SKU per facility | Confidence intervals required; flag low-confidence |
| Procurement Agent | Sonnet | Reorder point breach, forecast trigger | Generate draft POs, select vendor, calculate quantities | Spend limits; vendor whitelist; human approval above threshold |
| Rebalance Agent | Sonnet | Imbalance detection | Recommend inter-facility transfers | Cost ceiling; minimum transfer quantity |
| Orchestrator | Haiku | All events | Route to correct agent, maintain state | Audit log every decision |

---

## 8. Roadmap

### Phase 1: Simulation POC (DONE)
- DSP game agent via MCP
- Bottleneck detection, power analysis, logistics saturation
- 101 tests, 88% coverage
- Pitch deck for Skool community

### Phase 2: Agentic Simulation (4-6 weeks)
- Port DSP patterns to generic SCM simulation using Mesa + SimPy
- Beer-game-style multi-tier chain (Retailer -> Wholesaler -> Distributor -> Factory)
- Four agents (Signal, Forecast, Procurement, Rebalance) operating on simulation
- Dashboard showing agent decisions in real-time
- Measurable outcome: agents outperform manual play on bullwhip metric
- **Deliverable:** Live demo where Claude runs a supply chain better than a human

### Phase 3: Real Data Pilot (6-8 weeks)
- CSV/QuickBooks import for real distributor data
- Connect agents to real inventory data (read-only initially)
- Side-by-side comparison: agent recommendations vs. actual human decisions
- Track accuracy: did the agent's PO suggestions lead to better fill rate / lower inventory?
- **Deliverable:** "Shadow mode" running alongside one real distributor

### Phase 4: Product (12-16 weeks)
- Multi-tenant SaaS
- Graduation from shadow -> advisory -> autonomous (with guardrails)
- Pricing: $500/mo starter, $2K/mo pro, custom enterprise
- **Deliverable:** Paying customers

---

## 9. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| LLM hallucination causes bad PO | Medium | High | Human approval gate; spend limits; confidence scoring |
| SMB distributors won't trust AI | Medium | High | Shadow mode first; show recommendations alongside actuals |
| Data quality from SMB systems | High | Medium | Data validation layer; graceful handling of missing data |
| Competitor (o9, Kinaxis) moves downmarket | Low (18mo) | Medium | Speed advantage; they can't ship fast at low price points |
| LLM costs eat margin at scale | Medium | Medium | Haiku for routing, Sonnet only for reasoning; cache aggressively |
| Simulation doesn't match reality | Medium | High | Calibrate with real data in Phase 3; feedback loop |

---

## 10. Market Sizing (Napkin Math)

**TAM (Total Addressable Market):**
- SCM software market: $36.4B (2026)
- AI in supply chain: $14B (2025) -> $50B by 2031
- Supply chain simulation specifically: $1.87B -> $5.23B by 2030

**SAM (Serviceable Addressable Market):**
- US wholesale distributors: ~350,000 businesses
- $10M-$100M revenue segment: ~35,000 businesses
- Average software spend: $15K/yr
- SAM = ~$525M/yr

**SOM (Serviceable Obtainable Market -- Year 1):**
- Target: 50 paying customers at $12K/yr average
- SOM = $600K ARR
- Series A territory at $1-3M ARR requires 83-250 customers

---

## 11. Recommended Next Steps

### Immediate (This Week)
1. **Validate beachhead with real distributors.** Talk to 5 SMB wholesale distributors. Confirm the pain, pricing tolerance, and willingness to pilot. Use the pitch deck as-is.
2. **Fork mcp-dsp-game into `agentic-scm` repo.** Extract the 7 reusable patterns into a clean foundation.

### Short-Term (Weeks 1-4)
3. **Build the beer-game simulation.** Use Mesa + SimPy. Four-tier chain with stochastic demand. Get agents playing the beer game and beating the bullwhip effect.
4. **Record a demo video.** Claude managing a supply chain in real-time, explaining its reasoning in natural language. This is the "wow" moment for the Skool pitch.

### Medium-Term (Weeks 5-12)
5. **Find one pilot distributor.** Shadow mode: agent reads their data, makes recommendations, tracks accuracy against their actual decisions.
6. **Build the dashboard.** Next.js + Shadcn. Show inventory levels, agent recommendations, approval queue, outcome tracking.

### Decision Points
- **After 5 customer interviews:** Go/no-go on the SMB distributor beachhead. If pain isn't acute enough, pivot to 3PL or mid-market.
- **After beer-game demo:** Evaluate whether the agent architecture is good enough for real data, or needs fundamental changes.
- **After shadow pilot:** Decide if recommendations are accurate enough to graduate to advisory mode.

---

## Sources

### Market Data
- [IMARC Group - SCM Software Market Size](https://www.imarcgroup.com/supply-chain-management-software-market)
- [Technavio - SCM Software Market Growth](https://www.technavio.com/report/supply-chain-management-software-market-industry-analysis)
- [ReportPrime - Supply Chain Simulation Software Market](https://www.reportprime.com/supply-chain-simulation-software-r13269)
- [Fortune Business Insights - Agentic AI Market](https://www.fortunebusinessinsights.com/agentic-ai-market-114233)
- [Mordor Intelligence - Agentic AI Market](https://www.mordorintelligence.com/industry-reports/agentic-ai-market)

### Agentic SCM Thought Leadership
- [HBR - When Supply Chains Become Autonomous](https://hbr.org/2025/12/when-supply-chains-become-autonomous)
- [EY - Revolutionizing Global Supply Chains with Agentic AI](https://www.ey.com/en_us/insights/supply-chain/revolutionizing-global-supply-chains-with-agentic-ai)
- [IBM - Scaling Supply Chain Resilience with Agentic AI](https://www.ibm.com/thought-leadership/institute-business-value/en-us/report/supply-chain-ai-automation-oracle)
- [WEF - Autonomous Orchestration for Supply Chain Management](https://www.weforum.org/stories/2025/11/autonomous-orchestration-next-frontier-supply-chain-management/)
- [Inbound Logistics - AI in SCM 2026 Outlook](https://www.inboundlogistics.com/articles/ai-in-supply-chain-management-how-useful-will-it-be-in-2026/)
- [Dataiku - Supply Chain AI Trends 2026](https://www.dataiku.com/stories/blog/supply-chain-ai-trends-2026)
- [Kanerika - Agentic AI in Supply Chain 2026](https://kanerika.com/blogs/agentic-ai-in-supply-chain/)
- [Prolifics - Agentic AI in Supply Chain Trends](https://prolifics.com/usa/resource-center/blog/agentic-ai-in-supply-chain)

### Simulation Tools & Frameworks
- [AnyLogic - Simulation Modeling Software](https://www.anylogic.com/)
- [FlexSim - Supply Chain Simulation](https://www.flexsim.com/supply-chain-simulation/)
- [Mesa 3 - Agent-Based Modeling in Python (JOSS)](https://joss.theoj.org/papers/10.21105/joss.07668)
- [Gartner - Supply Chain Simulation Software Reviews](https://www.gartner.com/reviews/market/supply-chain-simulation-software)
- [MIT Sloan Beer Game Online](https://mitsloan.mit.edu/teaching-resources-library/mit-sloan-beer-game-online)

### Competitive Landscape
- [Flowlity - AI-Driven SCM Software Comparative](https://www.flowlity.com/resources/ai-in-supply-chain-planning-software-comparative-analysis)
- [DOSS - Best SCM Platforms 2026](https://www.doss.com/trends/8-best-supply-chain-management-platforms-in-2026)
- [Contrary Research - o9 Solutions Business Breakdown](https://research.contrary.com/company/o9-solutions)
- [Gartner - Kinaxis vs o9 Solutions](https://www.gartner.com/reviews/market/supply-chain-planning-solutions/compare/kinaxis-vs-o9-solutions)

### Distributor Pain Points
- [Gartner Digital Markets - Inventory Management Buyer Insights 2026](https://www.gartner.com/en/digital-markets/insights/stand-out-in-your-category-with-inventory-management-buyer-insights)
- [Phocas - Wholesale Distribution Management](https://www.phocassoftware.com/industries/wholesale-distribution)
- [HashMicro - Wholesale Distribution ERP Pain Points](https://www.hashmicro.com/blog/4-pain-points-of-wholesalers-and-distributors-which-erp-software-can-help/)
