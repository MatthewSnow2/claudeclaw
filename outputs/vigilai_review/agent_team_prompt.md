# Agent Team Prompt: VigilAI Autonomous Wingman -- Competition Readiness Review & Implementation Plan

## Directive

Create an agent team to review the VigilAI DCS Wingman codebase, assess competition readiness for Lockheed Martin's AI Fight Club (Q1 2026), and produce an actionable implementation plan to go from DCS mod to competition-ready autonomous wingman demonstrator.

## Context

**Product**: VigilAI DCS Wingman -- a premium AI wingman mod for DCS World (combat flight simulator) with advanced tactical decision-making, realistic sensor simulation, and comprehensive training capabilities.

**Current state (v1.0 -- COMPLETE)**:
- Written in Lua for DCS World's Mission Scripting Environment
- Formation flight controller with 95%+ accuracy
- 35+ voice commands across 6 categories (Whisper/Vosk/Azure)
- Combat engagement with weapon system, target evaluation, Pk calculation
- Survivability module with threat assessment, auto-abort at <25% survival probability
- Physics-based radar models: APG-68, APG-77, APG-81
- IRST systems: EOTS, PIRATE with environmental effects
- Tactical Decision Engine (TDE) with dynamic mission adaptation
- 5 mission types with dynamic objectives and 10-priority task switching
- Pilot coach with real-time feedback and 8 progressive training scenarios
- License validation, anti-piracy, installer system
- 108 tests, 100% pass rate, GitHub Actions CI/CD

**v1.1 planned but not started**: F-22/F-35/Su-57/Eurofighter profiles, multiplayer, advanced weather, improved NLP
**v1.2 future**: ML integration (adaptive behavior, learning from patterns), VR, expanded missions

**Target competition**: Lockheed Martin AI Fight Club -- competitive environment for AI autonomous systems, head-to-head bracket format, Q1 2026 timeline. Teams integrate their AI systems which are evaluated on performance in combat scenarios.

**Also relevant**: The CCA (Collaborative Combat Aircraft) program and broader autonomous wingman landscape. The US Air Force is actively pursuing drone wingman technology (Increment 1 with Boeing/Anduril prototypes, Increment 2 with Lockheed's Vectis concept).

**Repository**: /home/apexaipc/projects/vigilai-dcs-wingman/
**Built by**: M2AI (Matthew Snow's AI consultancy)

## Inputs

Source files to review:
- `/home/apexaipc/projects/vigilai-dcs-wingman/BLUEPRINT.md` -- project roadmap and status
- `/home/apexaipc/projects/vigilai-dcs-wingman/vigilai/README.md` -- project overview
- `/home/apexaipc/projects/vigilai-dcs-wingman/vigilai/docs/Architecture.md` -- system architecture
- `/home/apexaipc/projects/vigilai-dcs-wingman/vigilai/docs/API_Reference.md` -- API docs
- `/home/apexaipc/projects/vigilai-dcs-wingman/vigilai/docs/User_Guide.md` -- user guide
- Core source: `vigilai/src/core/tactical_decision_engine.lua`, `vigilai/src/core/sensor_simulation.lua`
- Combat: `vigilai/src/combat/combat_manager.lua`, `survivability.lua`, `weapon_system.lua`
- Mission: `vigilai/src/mission/mission_manager.lua`, `dynamic_objectives.lua`
- Formation: `vigilai/src/formation/formation_controller.lua`
- Voice: `vigilai/src/voice/voice_recognition.lua`
- Sensors: `vigilai/src/sensors/advanced_sensor_simulation.lua`
- Training: `vigilai/src/training/pilot_coach.lua`, `training_scenarios.lua`
- Tests: `vigilai/tests/` (all test files)
- CI: `.github/workflows/ci.yml`

## Team

Spawn 5 teammates:

### 1. Codebase Architect
**Mission**: Review the entire VigilAI codebase for architectural quality, modularity, extensibility, and competition readiness. Assess whether the current DCS-specific architecture can be adapted for a competition environment (which may use different simulation frameworks). Evaluate the Tactical Decision Engine as the core competitive asset.

**Deliverable**:
- Architecture assessment: strengths, weaknesses, coupling to DCS-specific APIs
- Modularity score: how easily can the TDE, sensor models, and combat logic be extracted from DCS and plugged into a different simulation environment?
- Code quality review: patterns, anti-patterns, tech debt items from BLUEPRINT.md
- Abstraction layer recommendations: what interface layer is needed between VigilAI's decision engine and any simulation backend?
- Competitive differentiator analysis: what makes this TDE unique vs other autonomous systems?
- Save to `outputs/vigilai_review/codebase_architecture.md`

### 2. Competition Intelligence Analyst
**Mission**: Research Lockheed Martin's AI Fight Club competition in detail. What are the rules, requirements, evaluation criteria, and submission format? What simulation environment will be used? What have past autonomous AI competitions (DARPA AlphaDogfight, AI Fight Club pilots) looked like? Map the competitive landscape -- who else is likely competing?

**Deliverable**:
- AI Fight Club competition brief: rules, timeline, evaluation criteria, prizes (research via web)
- Simulation environment requirements: what framework/simulator will be used?
- Entry requirements: team composition, registration, technical submissions
- Competitive landscape: who else builds autonomous air combat AI? (Shield AI, Heron Systems/Calspan, EpiSci, Collins Aerospace, academic teams)
- Gap analysis: what does VigilAI have vs what the competition likely requires?
- Lessons from DARPA AlphaDogfight Trials (2020): what worked, what didn't, what the winning teams did
- Analogous competitions: DARPA ACE, AI Fight Club, any 2026 open competitions
- Save to `outputs/vigilai_review/competition_intelligence.md`

### 3. AI/ML Strategy Advisor
**Mission**: VigilAI v1.0 uses rule-based decision making (the TDE). The v1.2 roadmap lists ML integration. For a competition, assess whether the current rule-based approach is competitive or whether ML (reinforcement learning, neural networks) is required. What's the minimum viable ML integration that would make VigilAI competitive?

**Deliverable**:
- Rule-based vs ML assessment: Can rule-based TDE compete against RL-trained agents?
- Competitive precedent: What did the DARPA AlphaDogfight winners use? (Heron Systems used deep RL)
- ML integration roadmap: if ML is needed, what's the fastest path?
  - Option A: Add RL layer on top of existing TDE (hybrid approach)
  - Option B: Train a neural network to replace TDE (full ML, higher ceiling, longer timeline)
  - Option C: Use the TDE as a training opponent for an ML agent
- Technology recommendations: frameworks (stable-baselines3, RLlib), simulation environments (JSBSim, FlightGear, custom), training infrastructure (GPU requirements)
- Timeline estimate: how long to go from current state to ML-capable?
- Risk assessment: can this be done in time for Q1 2026?
- Save to `outputs/vigilai_review/ml_strategy.md`

### 4. Implementation Planner
**Mission**: Produce a concrete, phased implementation plan to take VigilAI from "DCS World mod" to "competition-ready autonomous wingman." Consider the competition timeline (Q1 2026 -- possibly weeks away), available resources (one developer + AI assistance), and the existing codebase.

**Deliverable**:
- Phase-by-phase implementation plan:
  - Phase 0 (Week 1): Competition registration, rules confirmation, simulation environment setup
  - Phase 1: Core extraction -- abstract TDE from DCS into standalone decision engine
  - Phase 2: Competition environment integration -- adapt to whatever simulator the competition uses
  - Phase 3: Performance optimization -- tune decision-making for competition scoring criteria
  - Phase 4: Testing and validation -- head-to-head testing against baseline opponents
  - Phase 5: Submission preparation -- documentation, packaging, submission format
- Resource requirements: hardware, software, APIs, compute (GPU if ML needed)
- Critical path analysis: what must be done first, what can be parallelized?
- Risk register: technical risks, timeline risks, competition requirement risks
- Go/no-go decision points: at what stages should Matthew assess whether to continue?
- Save to `outputs/vigilai_review/implementation_plan.md`

### 5. Devil's Advocate
**Mission**: Challenge whether VigilAI can realistically compete. Be honest about the gap between a DCS World mod and a competition-ready autonomous system. Find the fatal flaws.

**Key challenges**:
- "A DCS mod is not a competition entry." DCS World is a consumer flight sim. Military competitions likely use different simulation environments (AFSIM, JSAF, custom). How much of the VigilAI code is reusable vs DCS-locked?
- "Rule-based AI lost to ML in 2020." Heron Systems beat all rule-based teams in DARPA AlphaDogfight using deep RL. Has the field moved further since then?
- "One person can't compete with defense contractors." Other teams have 10-50 engineers, millions in funding, and years of head start. What's M2AI's realistic angle?
- "The timeline is impossible." Q1 2026 is now. Is this already too late?
- "Lua is the wrong language." Competition environments likely use Python, C++, or custom APIs. The entire codebase would need porting.
- "Is this the right competition?" Maybe AI Fight Club isn't the right entry point. Are there smaller, more accessible competitions better suited to a solo developer?

**Deliverable**:
- Numbered objections with severity (Fatal / Serious / Manageable)
- Honest timeline assessment: can this realistically be done?
- Alternative competition recommendations (if AI Fight Club is too ambitious)
- "What would make this winnable?" -- the minimum path to a credible competition entry
- Save to `outputs/vigilai_review/devils_advocate.md`

## Dependencies

**Execution order**: Parallel fan-out, then Devil's Advocate reviews all.

- Agents 1-4 work in parallel
- Agent 5 (Devil's Advocate) works in parallel but should challenge findings from agents 1-4

## Synthesis

After all 5 agents complete:

1. Cross-reference: Does the Implementation Planner's timeline align with the Competition Intelligence? Does the ML Strategy match the competition's technical requirements?
2. Gap analysis: What's the delta between VigilAI's current state and competition entry requirements?
3. Produce a consolidated assessment:
   - GO / CONDITIONAL GO / NO-GO recommendation
   - If GO: concrete next 3 actions (this week)
   - If CONDITIONAL: what must be true for GO, and by when
   - If NO-GO: what's the alternative? (Different competition, commercial product instead, portfolio piece?)
   - Timeline: realistic calendar with milestones
   - Budget: estimated costs (compute, registration, tools)

Save to `outputs/vigilai_review/consolidated_assessment.md`
