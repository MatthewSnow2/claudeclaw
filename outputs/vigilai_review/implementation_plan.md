# VigilAI Competition Implementation Plan

**Target:** Lockheed Martin AI Fight Club (AIFC1) -- Spring 2026
**Author:** Implementation Planner (Claude Code)
**Date:** 2026-02-26
**Status:** PLAN -- Awaiting Go/No-Go on Phase 0 Intel

---

## Executive Summary

VigilAI is a complete DCS World mod (v1.0) with 8,500+ lines of Lua, 108 passing tests, and a mature Tactical Decision Engine (TDE). The codebase contains genuine tactical AI logic -- threat prioritization, survival probability calculation, sensor fusion, weapon selection, evasive maneuvering, and mission adaptation. This is not a toy project; it has real decision-making bones.

However, entering AI Fight Club requires significant work:
1. **Language gap**: VigilAI is Lua; competition environments are almost certainly Python-based
2. **API gap**: LM uses a proprietary synthetic environment, not DCS World
3. **Scale gap**: AIFC1 is 4v4 team combat, not 1v1 wingman support
4. **Intelligence gap**: The TDE uses rule-based heuristics, not ML; competitive entries will use RL

The plan below addresses each gap across 6 phases over approximately 5-6 weeks.

---

## Current Codebase Assessment

### What VigilAI Has (Transferable Assets)

| Module | LOC | Competition Value | Transfer Difficulty |
|--------|-----|-------------------|---------------------|
| `tactical_decision_engine.lua` | 442 | **HIGH** -- threat analysis, survival calc, weapon selection | Medium (logic ports cleanly) |
| `combat_manager.lua` | 518 | **HIGH** -- state machine (PASSIVE/DEFENSIVE/OFFENSIVE/EMERGENCY/ABORT) | Medium |
| `advanced_sensor_simulation.lua` | 702 | **MEDIUM** -- radar equation, IRST, sensor fusion (competition may abstract sensors) | Low (may not apply) |
| `survivability.lua` | 549 | **HIGH** -- threat assessment, abort logic | Medium |
| `weapon_system.lua` | 449 | **HIGH** -- Pk calculation, engagement evaluation | Medium |
| `formation_controller.lua` | ~300 | **HIGH** -- 4v4 needs formation tactics | Medium |
| `mission_manager.lua` + `dynamic_objectives.lua` | ~500 | **MEDIUM** -- mission adaptation logic | Low-Medium |

### What VigilAI Lacks

- **No RL/ML layer** -- all decisions are handcrafted heuristics
- **No Python codebase** -- everything is Lua 5.1
- **No multi-agent coordination** -- designed as single wingman, not 4-ship team
- **No competition API bindings** -- tightly coupled to DCS Mission Scripting Environment
- **No self-play training pipeline** -- no training infrastructure at all

---

## Phase 0 -- Competition Registration & Intel (Week 1)

**Objective:** Determine whether AIFC1 is viable for a solo developer with AI assistance, and gather the technical specifications needed for all subsequent phases.

### Tasks

| # | Task | Est. Hours | Owner |
|---|------|------------|-------|
| 0.1 | Email ai.fight.club.lm@lmco.com requesting: participant guide, eligibility requirements, API/SDK documentation, registration timeline, team size requirements | 0.5 | Matthew |
| 0.2 | Submit interest via LM's online contact form (https://www.lockheedmartin.com/en-us/capabilities/artificial-intelligence-machine-learning/ai-fight-club/ai-fight-club-contact.html) | 0.5 | Matthew |
| 0.3 | Research whether solo/indie teams are eligible (LM says "companies and teams of all sizes" but DOW qualifications may require clearances or organizational affiliation) | 2 | Matthew |
| 0.4 | Identify the simulation platform: LM's "synthetic environment" -- is it proprietary? Docker-based? What language are agent interfaces? | 0 (blocked on 0.1 response) | -- |
| 0.5 | Set up local development environment: Python 3.11, JSBSim, BVRGym, gymnasium, PyTorch, stable-baselines3 | 3 | Claude |
| 0.6 | Clone and test BVRGym (https://github.com/xcwoid/BVRGym) and LAG (https://github.com/liuqh16/LAG) as training environments while waiting for LM specs | 4 | Claude |
| 0.7 | Review Heron Systems' AlphaDogfight approach (winner of DARPA ACE trials) for architecture patterns | 2 | Claude |

### Dependencies
- 0.4 blocks all Phase 2 work
- 0.5 and 0.6 can proceed in parallel with 0.1-0.4

### Go/No-Go Criteria
- [ ] Eligibility confirmed (solo developer or small LLC accepted)
- [ ] Simulation environment docs received OR open-source alternative identified
- [ ] No security clearance requirements that exclude civilian participants
- [ ] Registration deadline has not passed (competition is Q1 2026 -- this is tight)
- [ ] Agent API is Python-compatible (or has documented interface spec)

### Risk Factors
- **CRITICAL: Timing.** It is February 26, 2026. AIFC1 is scheduled for "Q1 2026" (January-March). We may already be past registration or the event itself. This is the single biggest risk.
- **HIGH: Eligibility.** "DOW qualifications" suggests this may be restricted to defense contractors or organizations with existing LM relationships. A solo AI consultant may not qualify.
- **MEDIUM: Proprietary environment.** If LM requires agents to run inside their proprietary simulator with no local testing, development velocity drops dramatically.

---

## Phase 1 -- Core Extraction & Python Port (Weeks 1-2)

**Objective:** Extract VigilAI's decision-making logic from DCS-coupled Lua into simulator-agnostic Python modules.

### Tasks

| # | Task | Est. Hours | Owner |
|---|------|------------|-------|
| 1.1 | Create Python project scaffold: `vigilai-agent/` with `src/`, `tests/`, `configs/`, `training/` | 1 | Claude |
| 1.2 | Port `TacticalDecisionEngine` to Python: threat analysis, survival probability, weapon selection, evasive maneuvering, mission priority reassessment | 6 | Claude |
| 1.3 | Port `CombatManager` state machine to Python: PASSIVE/DEFENSIVE/OFFENSIVE/EMERGENCY/ABORT transitions, engagement queue, target prioritization | 4 | Claude |
| 1.4 | Port `Survivability` module: threat assessment, abort logic, damage modeling | 3 | Claude |
| 1.5 | Port `WeaponSystem`: Pk calculation, weapon scoring, engagement evaluation, launch parameters | 3 | Claude |
| 1.6 | Port `FormationController`: formation types, offset calculations, position management | 2 | Claude |
| 1.7 | Create simulator-agnostic interface layer (`AgentInterface` ABC) that defines: `observe(state) -> observation`, `decide(observation) -> action`, `act(action) -> result` | 3 | Claude |
| 1.8 | Port sensor fusion logic (simplified -- competition may abstract sensors, but the classification and confidence logic is valuable) | 2 | Claude |
| 1.9 | Write unit tests for all ported modules (target: equivalent coverage to existing 108 Lua tests) | 6 | Claude |
| 1.10 | Validate ported logic produces identical decisions to Lua originals on a shared test scenario set | 4 | Claude |

### Dependencies
- Can start immediately, independent of Phase 0 (except 0.5 for Python environment)
- Phase 1.7 (interface layer) will need refinement in Phase 2 once competition API is known

### Go/No-Go Criteria
- [ ] All ported modules pass unit tests
- [ ] TDE produces equivalent threat rankings to Lua version on 10+ test scenarios
- [ ] Combat state machine transitions match Lua behavior
- [ ] `AgentInterface` ABC is clean enough to implement against any simulator

### Risk Factors
- **LOW:** Lua-to-Python port is straightforward for this codebase (no complex Lua metatables or coroutines in the decision logic)
- **MEDIUM:** Some DCS-specific assumptions (e.g., coordinate systems, unit types) may be embedded deeper than obvious

### Architecture: Ported Module Structure

```
vigilai-agent/
  src/
    core/
      tactical_decision_engine.py   # From tactical_decision_engine.lua
      agent_interface.py            # New: simulator-agnostic ABC
    combat/
      combat_manager.py             # From combat_manager.lua
      survivability.py              # From survivability.lua
      weapon_system.py              # From weapon_system.lua
    sensors/
      sensor_fusion.py              # Simplified from advanced_sensor_simulation.lua
    formation/
      formation_controller.py       # From formation_controller.lua
    mission/
      mission_manager.py            # From mission_manager.lua
    adapters/
      jsbsim_adapter.py            # JSBSim/BVRGym adapter
      lm_adapter.py                # LM competition adapter (Phase 2)
      dcs_adapter.py               # Original DCS adapter (maintain compatibility)
  tests/
    test_tde.py
    test_combat_manager.py
    test_survivability.py
    test_weapon_system.py
    test_formation.py
    test_integration.py
  training/
    self_play.py                   # Phase 3
    reward_shaping.py              # Phase 3
  configs/
    f16_config.yaml                # Aircraft-specific parameters
    combat_params.yaml             # Engagement rules
```

---

## Phase 2 -- Competition Environment Integration (Weeks 2-3)

**Objective:** Connect the ported VigilAI agent to whatever simulation environment the competition uses. If LM's environment is not accessible, use BVRGym/LAG as a proxy.

### Tasks

| # | Task | Est. Hours | Owner |
|---|------|------------|-------|
| 2.1 | Implement competition-specific adapter (adapting `AgentInterface` to competition's state/action space) | 8 | Claude |
| 2.2 | Map competition observation space to VigilAI's internal state representation (position, velocity, attitude, fuel, weapons, contacts) | 4 | Claude |
| 2.3 | Map VigilAI's action decisions to competition's action space (maneuver commands, weapon release, formation commands) | 4 | Claude |
| 2.4 | Implement 4-ship team coordination layer (VigilAI only handles 1 wingman currently) | 8 | Claude + Matthew |
| 2.5 | Design team tactics: element lead/wingman pairs, mutual support, bracket maneuvers, pincer attacks | 6 | Matthew (domain) + Claude (implementation) |
| 2.6 | Implement BVRGym adapter as fallback training environment | 4 | Claude |
| 2.7 | Run baseline tests: VigilAI rule-based agent vs. BVRGym's built-in opponents | 4 | Claude |
| 2.8 | Implement LAG adapter for WVR (close combat) training | 3 | Claude |
| 2.9 | Performance profiling -- ensure agent can make decisions within competition's time budget (likely 100ms-1s per step) | 2 | Claude |

### Dependencies
- 2.1-2.3 blocked on Phase 0 results (competition API spec)
- 2.6-2.8 can proceed as fallback regardless of Phase 0
- 2.4-2.5 are the most critical new development

### Go/No-Go Criteria
- [ ] Agent loads and runs in competition environment (or proxy)
- [ ] 4-ship team executes coordinated tactics (not 4 independent agents)
- [ ] Decision latency < competition time budget
- [ ] Agent beats at least one baseline opponent

### Risk Factors
- **HIGH: 4v4 coordination.** This is the biggest development gap. VigilAI has zero multi-agent coordination. Building this from scratch in 1-2 weeks is ambitious.
- **HIGH: Unknown API.** If LM's simulator uses a radically different state/action representation, adapter work could expand significantly.
- **MEDIUM: Action space mismatch.** VigilAI thinks in terms of "engage target X" or "execute defensive turn left"; the competition may require low-level stick/throttle commands.

### Team Coordination Architecture (New Development)

```
TeamCoordinator
  |
  +-- Element 1 (Lead + Wingman)
  |     |-- Lead: TDE instance (offensive focus)
  |     |-- Wing: TDE instance (defensive/support focus)
  |     |-- Mutual support logic
  |
  +-- Element 2 (Lead + Wingman)
  |     |-- Lead: TDE instance
  |     |-- Wing: TDE instance
  |     |-- Mutual support logic
  |
  +-- Team Tactics Layer
        |-- Target deconfliction (no two aircraft engage same target without authorization)
        |-- Formation selection (combat spread, wall, fluid four)
        |-- Bracket/pincer coordination
        |-- RTB/fuel management across team
```

---

## Phase 3 -- ML Augmentation (Weeks 3-4, if applicable)

**Objective:** Layer reinforcement learning on top of the rule-based TDE to handle the maneuvering decisions that heuristics cannot optimize.

### Tasks

| # | Task | Est. Hours | Owner |
|---|------|------------|-------|
| 3.1 | Define observation space for RL agent (own state + relative threat states, normalized) | 3 | Claude |
| 3.2 | Define action space (discrete: high-level maneuver choices; or continuous: stick/throttle) | 3 | Claude |
| 3.3 | Design reward function: kills (+), deaths (-), survival time (+), fuel efficiency (+), formation cohesion (+), mission objectives (+) | 4 | Matthew + Claude |
| 3.4 | Implement PPO training pipeline using stable-baselines3 or CleanRL | 6 | Claude |
| 3.5 | Use TDE as expert demonstration data for behavioral cloning (warm-start the RL policy) | 4 | Claude |
| 3.6 | Train against scripted opponents (BVRGym/LAG baselines) -- initial 1v1 | 8 (compute) | GPU |
| 3.7 | Extend to 4v4 self-play with team coordination | 10 | Claude |
| 3.8 | Implement hierarchical RL: high-level TDE selects tactics, low-level RL executes maneuvers | 6 | Claude |
| 3.9 | Validate ML agent matches or exceeds TDE performance on benchmark scenarios | 4 | Claude |
| 3.10 | Hyperparameter sweep (learning rate, reward weights, network architecture) | 6 (compute) | GPU |

### Dependencies
- Requires Phase 2 environment integration
- 3.5 requires Phase 1 ported TDE
- 3.6-3.7 require GPU compute (see Resource Requirements)

### Go/No-Go Criteria
- [ ] RL agent wins > 60% of 1v1 engagements against scripted baseline
- [ ] RL agent wins > 50% of 4v4 engagements against scripted baseline
- [ ] No performance regression vs. pure TDE on structured scenarios
- [ ] Training is stable (no reward collapse or divergence)

### Risk Factors
- **HIGH: Training time.** 4v4 multi-agent RL is computationally expensive. Without a serious GPU, training may not converge in time.
- **HIGH: Reward shaping.** Bad reward functions produce degenerate policies. This requires careful iteration.
- **MEDIUM: Sim-to-competition transfer.** If training on BVRGym but competing in LM's environment, the policy may not transfer.

### Hybrid Architecture (TDE + RL)

```
Observation -> TDE (rule-based)  -> Tactical Assessment
                                      |
                                      v
                                 RL Policy Network
                                      |
                                      v
                              Low-Level Maneuver Commands
                              (stick, throttle, weapon release)

TDE provides: threat ranking, recommended engagement type, survival assessment
RL learns:    optimal execution of TDE recommendations, novel tactics TDE can't discover
```

This hybrid approach has precedent -- it mirrors how DARPA ACE structured their agents (human-level strategy + AI maneuvering).

---

## Phase 4 -- Optimization & Testing (Weeks 4-5)

**Objective:** Harden the agent for competition conditions. Find and fix edge cases. Maximize scoring.

### Tasks

| # | Task | Est. Hours | Owner |
|---|------|------------|-------|
| 4.1 | Analyze competition scoring criteria and tune agent behavior to maximize points (not just kills) | 4 | Matthew + Claude |
| 4.2 | Stress test: 100+ simulated matches with random initial conditions | 6 (compute) | GPU |
| 4.3 | Edge case testing: low fuel, damaged systems, outnumbered scenarios, head-on merges | 4 | Claude |
| 4.4 | Test against diverse opponent strategies: aggressive, defensive, evasive, kamikaze, formation-heavy | 6 | Claude |
| 4.5 | Ablation study: disable each component and measure performance delta | 4 | Claude |
| 4.6 | Latency optimization: ensure all decisions complete within time budget under worst case | 3 | Claude |
| 4.7 | Memory profiling: ensure agent stays within any resource constraints | 2 | Claude |
| 4.8 | Implement graceful degradation: if ML inference fails, fall back to pure TDE | 2 | Claude |
| 4.9 | Record and analyze losing matches -- identify systematic weaknesses | 4 | Matthew + Claude |
| 4.10 | Final tuning pass on combat parameters (engagement ranges, Pk thresholds, abort criteria) | 3 | Claude |

### Dependencies
- Requires Phase 3 trained agent (or Phase 2 rule-based agent if ML is dropped)
- 4.1 requires competition scoring criteria (Phase 0)

### Go/No-Go Criteria
- [ ] Win rate > 65% against diverse opponent pool
- [ ] No crashes or hangs in 100+ matches
- [ ] All decisions complete within time budget
- [ ] Graceful degradation confirmed working
- [ ] Team coordination functions under adversity (agent loss, comms degradation)

### Risk Factors
- **MEDIUM: Overfitting to training opponents.** Agent may perform well against known baselines but fail against novel strategies.
- **LOW: Technical failures.** The fallback-to-TDE mechanism mitigates ML-specific failure modes.

---

## Phase 5 -- Submission & Documentation (Final Week)

**Objective:** Package, document, and submit the agent. Prepare for any presentation requirements.

### Tasks

| # | Task | Est. Hours | Owner |
|---|------|------------|-------|
| 5.1 | Package agent per competition submission format (likely Docker container or Python package) | 3 | Claude |
| 5.2 | Write technical documentation: architecture overview, design decisions, algorithm descriptions | 4 | Claude |
| 5.3 | Create demo video showing agent performance in simulation (if required) | 4 | Matthew |
| 5.4 | Prepare presentation slides (if competition includes presentation component) | 3 | Matthew + Claude |
| 5.5 | Final integration test in clean environment (fresh install, no development dependencies) | 2 | Claude |
| 5.6 | Submit via competition portal | 0.5 | Matthew |
| 5.7 | Post-mortem document: what worked, what didn't, lessons learned, future improvements | 2 | Claude |

### Dependencies
- 5.1 format depends on Phase 0 competition specs
- 5.5 should be done on a separate machine or clean Docker container

### Go/No-Go Criteria
- [ ] Submission package runs successfully in clean environment
- [ ] All required documentation complete
- [ ] Submission uploaded before deadline

### Risk Factors
- **LOW: Packaging.** Standard Python packaging is well-understood.
- **MEDIUM: Unknown submission requirements.** LM may require specific formats, signed artifacts, or security scans.

---

## Resource Requirements

### Hardware

| Resource | Need | Current | Gap | Cost Estimate |
|----------|------|---------|-----|---------------|
| Development Machine | i7+, 32GB RAM | HP ProBook 450 G10, i7-1355U, 32GB | **Sufficient** | $0 |
| GPU (Training) | NVIDIA RTX 3080+ or equivalent | **None** | **CRITICAL** | $200-500/mo cloud |
| GPU (Inference) | Not required (CPU inference OK for <1s decision budget) | N/A | None | $0 |

### GPU Options (Ranked by Preference)

1. **Lambda Labs** -- $1.10/hr for A10 (24GB). ~$200 for 200 hours of training. Best price/performance.
2. **Vast.ai** -- $0.30-1.00/hr for consumer GPUs. Cheapest but less reliable.
3. **AWS g4dn.xlarge** -- $0.53/hr Spot. Familiar from previous EC2 usage.
4. **RunPod** -- $0.44/hr for RTX 4090. Good middle ground.
5. **Local GPU** -- Buy a used RTX 3080 ($300-400). Permanent asset, but only worth it if continuing ML work.

### Software & APIs

| Software | Purpose | Cost |
|----------|---------|------|
| Python 3.11+ | Agent development | Free |
| PyTorch 2.x | ML framework | Free |
| stable-baselines3 | RL algorithms | Free |
| JSBSim | Flight dynamics | Free (open source) |
| BVRGym | BVR training env | Free (open source) |
| LAG | WVR training env | Free (open source) |
| LM Synthetic Environment | Competition sim | TBD (provided by LM?) |

### Estimated Total Cost

| Scenario | GPU Compute | Other | Total |
|----------|-------------|-------|-------|
| Minimal (rule-based only, no ML) | $0 | $0 | **$0** |
| Standard (100hrs GPU training) | ~$150 | $0 | **~$150** |
| Full (400hrs GPU, extensive training) | ~$500 | $0 | **~$500** |

---

## Critical Path

The critical path determines the minimum sequence of work that must complete for a viable submission:

```
Phase 0.1-0.3 (Registration Intel)        [WEEK 1, BLOCKING]
       |
       v
Phase 0 Go/No-Go Decision                 [END OF WEEK 1]
       |
       +-------> NOT VIABLE: Pivot to alternative competitions (see below)
       |
       v (VIABLE)
Phase 1.2-1.5 (Core Python Port)          [WEEKS 1-2, PARALLEL WITH 0]
       |
       v
Phase 2.1-2.5 (Environment + 4v4)         [WEEKS 2-3]
       |
       v
Phase 4.1-4.8 (Testing)                   [WEEKS 4-5]
       |
       v
Phase 5.1-5.6 (Submission)                [FINAL WEEK]
```

**Note:** Phase 3 (ML) is on the critical path only if the competition favors ML-based agents. A well-tuned rule-based TDE with 4v4 coordination may be competitive, especially against teams that have ML but lack domain knowledge. The TDE already encodes real tactical doctrine.

### What MUST Be Done First

1. **Send the inquiry email to LM.** Nothing else matters if we can't participate.
2. **Start the Python port immediately** -- this is useful regardless of competition outcome.
3. **Set up BVRGym locally** -- provides a training environment whether or not LM's sim is available.

---

## Parallel Workstreams

### What Matthew and Claude Can Work On Simultaneously

| Matthew | Claude |
|---------|--------|
| Competition registration and LM communication | Python project scaffold and module porting |
| Domain expertise: 4v4 air combat tactics, formation doctrine | Implementation of team coordination algorithms |
| Reward function design (what matters tactically) | RL pipeline implementation and training |
| Demo video creation | Agent optimization and testing |
| Presentation and documentation review | Code packaging and submission preparation |
| Contact defense industry network for competition intel | Research prior competition winners' approaches |

### Independent Work Tracks

**Track A (Claude-Led): Core Engineering**
- Python port of all Lua modules
- Test suite development
- Simulator adapter implementation
- RL training pipeline
- Performance optimization

**Track B (Matthew-Led): Strategy & Integration**
- Competition registration
- 4v4 tactical doctrine design
- Scoring criteria analysis
- Presentation/demo materials
- Business case for M2AI portfolio value

---

## Alternative Paths

If AI Fight Club is not viable (timing, eligibility, or technical barriers), here are ranked alternatives:

### Tier 1 -- Directly Relevant Competitions

| Competition | Status | Fit | Notes |
|-------------|--------|-----|-------|
| **DARPA AIR (Artificial Intelligence Reinforcements)** | Active program | HIGH | Successor to ACE. May have future open challenges. Check darpa.mil/research/programs/artificial-intelligence-reinforcements |
| **IEEE SaTML 2026 Competitions** | Open | MEDIUM | Academic focus, may include adversarial AI challenges |
| **IFAC 2026 Competitions** | Open (Busan, July 2026) | MEDIUM | Control systems focus, potential UAV/autonomous vehicle tracks |

### Tier 2 -- Adjacent Competitions (Build Portfolio)

| Competition | Status | Fit | Notes |
|-------------|--------|-----|-------|
| **AUVSI XPONENTIAL** | Annual (April-May) | MEDIUM | Autonomous systems expo with competitions |
| **NeurIPS Multi-Agent RL Competitions** | Annual (Dec) | MEDIUM | General MARL but applicable skills |
| **Kaggle Simulations** | Rolling | LOW-MEDIUM | Past: Hungry Geese, Lux AI. Check for new combat/strategy games |

### Tier 3 -- Build & Publish (No Competition Needed)

Even without a formal competition, the VigilAI Python port + RL pipeline is valuable as:

1. **Open-source showcase** -- "AI Air Combat Agent built with domain-expert heuristics + RL" is a strong M2AI portfolio piece
2. **Technical blog series** -- Document the port from Lua DCS mod to Python RL agent
3. **BVRGym leaderboard** -- If BVRGym has community benchmarks, top them
4. **Paper submission** -- The TDE-as-expert-policy + RL approach is publishable (arXiv, at minimum)
5. **Defense contractor pitch** -- Use the agent as a demo for consulting engagements with defense firms

### Recommended Fallback Strategy

If AIFC1 timing doesn't work:

1. Complete Phases 1-3 anyway (the Python port and RL pipeline are independently valuable)
2. Target BVRGym/LAG benchmarks as near-term validation
3. Publish results on GitHub and write up the architecture
4. Apply to AIFC2 or AIFC3 (LM plans ongoing events across air, land, sea, space)
5. Use the codebase to pitch defense consulting engagements

---

## Timeline Summary

```
Week 1 (Feb 26 - Mar 4):
  [Phase 0] Registration inquiry + intel gathering
  [Phase 1] Python project setup + begin core port
  [Phase 0] BVRGym/LAG setup as proxy training env

Week 2 (Mar 5 - Mar 11):
  [Phase 0] GO/NO-GO DECISION
  [Phase 1] Complete core module porting + tests
  [Phase 2] Begin environment integration + 4v4 design

Week 3 (Mar 12 - Mar 18):
  [Phase 2] Complete 4v4 coordination layer
  [Phase 2] Baseline testing against opponents
  [Phase 3] Begin RL pipeline (if GPU available)

Week 4 (Mar 19 - Mar 25):
  [Phase 3] RL training + hybrid TDE+RL integration
  [Phase 4] Begin optimization and stress testing

Week 5 (Mar 26 - Apr 1):
  [Phase 4] Final testing and edge case hardening
  [Phase 5] Packaging, documentation, submission

Buffer (Apr 2-7):
  [Phase 5] Contingency for delays
```

### Total Estimated Hours

| Phase | Claude Hours | Matthew Hours | GPU Hours | Total |
|-------|-------------|---------------|-----------|-------|
| Phase 0 | 9 | 3 | 0 | 12 |
| Phase 1 | 34 | 0 | 0 | 34 |
| Phase 2 | 39 | 6 | 0 | 45 |
| Phase 3 | 37 | 4 | 14 | 55 |
| Phase 4 | 34 | 4 | 6 | 44 |
| Phase 5 | 9 | 7.5 | 0 | 16.5 |
| **Total** | **162** | **24.5** | **20** | **206.5** |

Matthew's time commitment: approximately 5 hours/week for 5 weeks. Manageable alongside consulting work.

---

## Honest Assessment

### Strengths Going In
- **Real tactical logic** -- The TDE is not a demo. It implements actual threat prioritization, survival probability, weapon selection, and evasive maneuvering.
- **Domain knowledge** -- Many ML teams will have strong algorithms but weak domain modeling. VigilAI's heuristics encode real air combat doctrine.
- **Rapid AI-assisted development** -- Claude Code can port, test, and iterate far faster than a solo developer manually.
- **Hybrid architecture** -- TDE-as-expert-policy is a proven approach (Heron Systems used similar for AlphaDogfight).

### Weaknesses
- **Timing is the biggest risk.** AIFC1 may have already closed registration or may happen before we're ready.
- **No GPU** -- ML training requires compute that isn't locally available.
- **Solo team** -- Most competitors will be organizations with dedicated teams.
- **Unknown competition environment** -- We're building blind until LM provides specs.

### Bottom Line
The Lua TDE is genuinely transferable. The Python port is worth doing regardless of competition outcome. If AIFC1 timing works, a well-tuned rule-based agent with 4v4 coordination could place respectably even without ML. With ML augmentation, it could be competitive.

**Immediate action: Send the LM inquiry email today. Everything else flows from that.**
