# VigilAI Competition Intelligence Report

**Date**: 2026-02-26
**Analyst**: Competition Intelligence (Claude)
**Classification**: Internal -- Strategic Planning

---

## Table of Contents

1. [Lockheed Martin AI Fight Club](#1-lockheed-martin-ai-fight-club)
2. [DARPA AlphaDogfight Trials (2020)](#2-darpa-alphadogfight-trials-2020)
3. [DARPA ACE Program (2020-2026)](#3-darpa-ace-program-2020-2026)
4. [Other AI Air Combat Competitions](#4-other-ai-air-combat-competitions-2025-2026)
5. [Competitive Landscape](#5-competitive-landscape)
6. [Gap Analysis: VigilAI vs Competition Requirements](#6-gap-analysis-vigilai-vs-competition-requirements)
7. [Recommendations](#7-recommendations)

---

## 1. Lockheed Martin AI Fight Club

### Overview

AI Fight Club is a Lockheed Martin-hosted virtual proving ground for military AI algorithms, announced June 3, 2025. It creates a Pentagon-grade evaluation environment that smaller vendors and teams can access without building their own DoD-standard testing infrastructure.

**Contact**: ai.fight.club.lm@lmco.com | https://www.lockheedmartin.com/AIFightClub

### Timeline

| Milestone | Date |
|-----------|------|
| Program announced | June 3, 2025 |
| Simulation environment completion | Q3 2025 (planned) |
| AIFC1 (first competition) | Originally Q4 2025; **slipped to Q1/Spring 2026** |
| Current status (Feb 2026) | No public announcement of AIFC1 having occurred yet |

**Assessment**: As of February 2026, AIFC1 appears to still be upcoming. The schedule slipped from Q4 2025 to "first quarter 2026" / "spring 2026." No public results or event coverage has surfaced, suggesting it either hasn't happened yet or is imminent.

### Competition Format

- **Scenario**: Teams of 4 AI-piloted 4th-generation aircraft in virtual air-to-air combat
- **Objective**: Dominate the enemy, take minimal losses
- **Structure**: Head-to-head bracket matchups
- **Domains planned**: Air (first), then land, sea, space in future events
- **Government observers** present during competitions

### Simulation Environment

- Custom synthetic environment developed by Lockheed Martin
- Simulates realistic scenarios across air, land, sea, and space domains
- Uses "government-approved models and simulation tools"
- Incorporates DoD qualification requirements into its scoring framework
- Specific technical stack (programming languages, APIs) not publicly disclosed
- Participants receive a "Participant Guide" with challenge scenario, scoring, evaluation criteria, and **interface requirements**

### Evaluation Criteria

- Predetermined metrics informed by Operations Analysis
- Metrics shared with competitors before the event
- Must meet "Department of War (DOW) standards"
- Performance evaluated on: combat effectiveness, loss minimization, integration potential

### Eligibility

- **Open to companies and teams of all sizes** -- explicitly designed for smaller vendors
- Industry and academia welcome
- Teams should include "experts in AI development, military operations, and domain-specific knowledge"
- No stated restriction to US-only participants (though defense context implies ITAR/export considerations)
- No specific team size requirements published

### IP Protection and Prizes

- "What happens inside that environment will stay within that environment" (Fight Club rules)
- No monetary prizes announced
- **Strategic incentive**: Top performers gain partnership opportunities with Lockheed Martin
- LM directs ~60% of its $70B+ annual revenue to suppliers -- this is a supplier pipeline
- Teams can publish and present research findings

### Key Unknowns

- Exact technical API/SDK for agent integration
- Whether DCS World, JSBSim, AFSIM, or a custom sim is used internally
- Security clearance requirements (if any)
- Whether the sim environment SDK will be distributed to teams for local development
- Registration deadline
- Maximum number of teams

---

## 2. DARPA AlphaDogfight Trials (2020)

### Background

DARPA's AlphaDogfight Trials (ADT) were a 2019-2020 competition pitting AI agents against each other and against a human F-16 pilot in simulated within-visual-range (WVR) dogfights.

### Timeline

| Phase | Date |
|-------|------|
| Trial 1 | October 2019 |
| Trial 2 | January 2020 |
| Trial 3 (Finals) | August 18-20, 2020 |
| Venue | Johns Hopkins APL (virtual, streamed live) |

### Participants (8 teams)

| Team | Result | Approach |
|------|--------|----------|
| **Heron Systems** | **Winner** -- beat all AI teams AND human pilot 5-0 | Deep RL (model-free), "Falco" agent |
| Lockheed Martin | 2nd place | RL-based |
| Aurora Flight Sciences | 3rd place | RL-based |
| PhysicsAI | 4th place | Physics-informed RL |
| Georgia Tech Research Institute (GTRI) | Eliminated earlier | Hierarchical RL |
| EpiSci | Eliminated earlier | Hybrid ML |
| Perspecta Labs | Eliminated earlier | Various |
| SoarTech | Eliminated earlier | Cognitive architecture |

### Simulation Environment

- **JSBSim** (open-source flight dynamics model) for F-16 physics
- Observation space: ownship state (fuel, thrust, control surfaces, health), aerodynamics (alpha/beta), position (local coordinates, velocity, acceleration), attitude (Euler angles), opponent state
- Action space: continuous control inputs at 50 Hz simulation frequency
- Single aircraft 1v1 WVR guns-only dogfight

### Key Technical Findings

1. **Deep RL dominated**: Heron's "Falco" agent used model-free deep RL with 4+ billion training iterations
2. **Hierarchical RL showed promise**: GTRI used a high-level policy selector + low-level specialized policies (off-policy, maximum entropy methods with expert reward shaping)
3. **Rule-based and scripted approaches lost**: Teams relying heavily on predefined maneuvers or expert systems were outperformed by learned policies
4. **"Superhuman aiming"**: The winning agent achieved precision in gun targeting that human pilots could not match
5. **Human pilot's assessment**: The human pilot noted the AI's aggression was unlike anything he'd faced -- no hesitation, no fear, optimal energy management

### Lessons for VigilAI

- Rule-based Tactical Decision Engines (TDE) were exactly the kind of approach that lost in ADT
- The winning agents needed massive compute for training (billions of iterations)
- JSBSim is the de facto standard for research-grade flight dynamics
- 1v1 WVR is the simplest scenario; multi-agent (4v4) is significantly harder

---

## 3. DARPA ACE Program (2020-2026)

### Overview

The Air Combat Evolution (ACE) program is the successor to AlphaDogfight, focused on transitioning AI from simulation to real aircraft and building trust in combat autonomy.

### Key Milestones

| Date | Achievement |
|------|-------------|
| 2020 | Program launch, selected performers |
| Dec 2022 | First upload of AI algorithms to X-62A VISTA at Edwards AFB |
| 2023 | 21 test flights (Dec 2022 - Sep 2023), AI vs manned F-16 at 1,200 mph, within 2,000 ft |
| 2024 | World-first: AI-controlled jet dogfights against manned aircraft declared |
| Feb 2026 | Lockheed Martin Skunk Works tests missile-evasion AI with direct aircraft control on X-62A |

### ACE Performers

| Organization | Role |
|-------------|------|
| EpiSci | Tactical AI algorithms ($7.4M contract) |
| PhysicsAI | Flight AI algorithms |
| Shield AI (Heron Systems) | Autonomy AI |
| Johns Hopkins APL | Integration and test |
| Calspan | X-62A VISTA aircraft operation |
| Cubic Defense | Red/Blue force simulation |

### X-62A VISTA Platform

- Modified F-16D operated by Calspan at Edwards AFB
- Software-configurable to mimic flight characteristics of other aircraft
- Safety pilots on board with override capability
- Receiving Mission Systems Upgrade: Raytheon PhantomStrike AESA radar
- In Feb 2026: Lockheed testing autonomous missile-evasion capability with direct AI control

### Relationship to AI Fight Club

- ACE demonstrated that simulation-trained AI can transfer to real aircraft
- AI Fight Club is LM's commercial extension of this concept -- a proving ground for new entrants
- ACE performers (Shield AI, EpiSci) are likely to be strong AI Fight Club competitors or advisors
- The DoD evaluation standards used in AI Fight Club are likely informed by ACE program learnings

---

## 4. Other AI Air Combat Competitions (2025-2026)

### Active/Upcoming Competitions

| Competition | Host | Status | Accessibility |
|------------|------|--------|---------------|
| **AI Fight Club** | Lockheed Martin | AIFC1 Q1/Spring 2026 | Open to all team sizes |
| **A2RL Autonomous Drone Championship** | Abu Dhabi | Ongoing | High-speed drone racing + AI |
| **AFA CyberPatriot / Aerial Drone Competition** | REC Foundation / DSEC | 2025-2026 season | Primarily educational teams |
| **UAS4STEM International** | AMA | 2026 season open | International, educational focus |

### Competitions Using Commercial Sims

- **No known major competitions use DCS World** as an official platform
- DCS World has an active modding community for AI improvements, but these are hobbyist-level
- The Harfang 3D Dogfight Sandbox is an open-source Python alternative used in some research
- Most serious competitions use custom sims (DARPA) or JSBSim-based environments

### Government/Military Programs (Not Open Competitions)

| Program | Description |
|---------|-------------|
| **CCA Program** | USAF Collaborative Combat Aircraft -- 1,000 autonomous drones by 2030 |
| **AFRL Research** | Ongoing AI air combat research, uses AFSIM internally |
| **DAF-MIT AI Accelerator** | 5-year partnership renewed 2024, Test Pilot School workshops |

### Assessment

The AI Fight Club is currently the **only major open competition** specifically focused on AI air combat algorithms that accepts teams of all sizes. There is no equivalent to Kaggle or HackerRank for military AI dogfighting. The space is dominated by government programs with restricted access.

---

## 5. Competitive Landscape

### Tier 1: Well-Funded Defense AI Companies

| Company | Valuation/Size | Key Product | Sim Framework | Status |
|---------|---------------|-------------|---------------|--------|
| **Shield AI** | $5.6B (2025) | Hivemind autonomy stack | Custom + JSBSim heritage | CCA program, V-BAT combat-proven (130+ sorties in Ukraine), F-16 autonomy |
| **Anduril Industries** | $14B+ | Lattice OS + Fury (YFQ-44A) | Custom (Lattice) | First "fighter" designation for a drone (Feb 2026), weapons integration testing |
| **EpiSci** | Private | Tactical AI (hybrid ML) | Custom | $7.4M DARPA ACE contract, flew on X-62A |

### Tier 2: Major Defense Contractors

| Company | AI Capability | Notes |
|---------|--------------|-------|
| **Lockheed Martin** | Skunk Works AI, AI Fight Club host | 2nd place ADT, X-62A missile-evasion AI (Feb 2026) |
| **Collins Aerospace (RTX)** | "Sidekick" CCA autonomy | 4+ hour autonomous CCA flight on YFQ-42A |
| **Boeing** | MQ-28 Ghost Bat, AFSIM (original dev) | Loyal wingman for RAAF |
| **General Atomics** | YFQ-42A CCA platform | Hardware platform, integrates Collins/Shield AI software |
| **Northrop Grumman** | CCA competitor (YFQ-42 contender) | Classified programs |

### Tier 3: Academic and Research

| Institution | Focus | Relevance |
|------------|-------|-----------|
| **Johns Hopkins APL** | ACE integration, ADT host | Neutral evaluator role |
| **MIT (DAF AI Accelerator)** | AI pilot training, RL research | 5-year DoD partnership |
| **Georgia Tech (GTRI)** | Hierarchical RL for air combat | ADT participant, published research |
| **USAF Test Pilot School** | X-62A operations, AI flight test | Real-aircraft AI validation |

### Simulation Frameworks in Use

| Framework | Type | Used By | Accessibility |
|-----------|------|---------|---------------|
| **JSBSim** | Open-source FDM (C++) | DARPA ADT, academic research | Fully open, Python bindings |
| **AFSIM** | Gov't-owned M&S (C++) | AFRL, DoD wargaming | USG/cleared contractors only |
| **Lattice** | Proprietary | Anduril | Closed |
| **Hivemind** | Proprietary | Shield AI | Closed |
| **DCS World** | Commercial game sim (Lua) | Hobbyists, limited research | Commercial license, Lua API |
| **Harfang 3D Dogfight** | Open-source (Python) | Research, prototyping | Fully open |
| **LAG (JSBSim+Gym)** | Open-source (Python) | Academic RL research | Fully open, 1v1 and 2v2 |
| **BVR Gym** | Open-source (Python) | Beyond-visual-range research | Fully open |
| **Tunnel** | Open-source (Python) | F-16 RL training | Fully open, <300 lines |

---

## 6. Gap Analysis: VigilAI vs Competition Requirements

### What VigilAI Has

| Capability | Details |
|-----------|---------|
| Simulation platform | DCS World |
| Scripting language | Lua |
| Decision architecture | Rule-based Tactical Decision Engine (TDE) |
| Sensor modeling | Physics-based sensor simulation |
| Test coverage | 108 tests |
| Domain focus | Autonomous wingman behaviors |

### What Competitions Typically Require

| Requirement | AI Fight Club | DARPA ADT/ACE | Open Research |
|------------|---------------|---------------|---------------|
| Language/API | TBD (likely Python/C++) | Python + JSBSim C++ | Python (Gymnasium) |
| Sim platform | LM proprietary | JSBSim | JSBSim, custom |
| AI approach | ML/RL expected to dominate | Deep RL won decisively | RL (PPO, SAC, etc.) |
| Multi-agent | 4v4 (AIFC1) | 1v1 (ADT), multi (ACE) | 1v1, 2v2 |
| DoD standards | DOW qualification framework | DARPA evaluation | N/A |
| Real-time perf | Required | Required | Varies |

### Critical Gaps

#### Gap 1: Rule-Based vs Learning-Based Architecture (CRITICAL)

**Current**: VigilAI uses a rule-based TDE.
**Required**: Every winning and top-performing system in DARPA ADT used deep reinforcement learning. Rule-based systems were categorically outperformed.

**Impact**: A rule-based system entering AI Fight Club would likely be non-competitive. The DARPA ADT demonstrated conclusively that hand-coded rules cannot match learned policies in dynamic air combat.

**Remediation**: Implement RL training pipeline (PPO, SAC, or hierarchical RL). The TDE could serve as an expert prior for reward shaping or as a fallback safety layer, but should not be the primary decision-maker.

#### Gap 2: Simulation Platform Lock-in (HIGH)

**Current**: VigilAI is built on DCS World with Lua scripting.
**Required**: AI Fight Club uses a Lockheed Martin proprietary sim. DARPA used JSBSim. Most research uses JSBSim + Gymnasium.

**Impact**: DCS World is not used by any serious competition or government program. The Lua API is limited compared to JSBSim's Python/C++ bindings. DCS World's commercial license may also restrict competition use.

**Remediation**: Port core logic to Python. Use JSBSim as the primary flight dynamics model. Wrap in Gymnasium interface for RL training. DCS World can remain as a visualization/validation layer.

#### Gap 3: Programming Language (MEDIUM-HIGH)

**Current**: Lua
**Required**: Python (RL frameworks: PyTorch, TensorFlow, Stable-Baselines3) and C++ (JSBSim, performance-critical code)

**Impact**: The entire ML/RL ecosystem is Python-first. No major RL framework has Lua bindings. Integration with competition sim environments will require Python or C++ interfaces.

**Remediation**: Rewrite agent logic in Python. Use PyTorch or JAX for neural network policies. Keep Lua only for DCS World-specific scripting if needed.

#### Gap 4: Multi-Agent Coordination (MEDIUM)

**Current**: VigilAI focuses on autonomous wingman (likely 1v1 or lead-wing pair).
**Required**: AI Fight Club AIFC1 is 4v4 (teams of 4 AI-piloted aircraft).

**Impact**: 4v4 requires cooperative multi-agent RL (MARL), communication protocols between friendly agents, and team-level strategy -- fundamentally different from single-agent wingman behavior.

**Remediation**: Implement MARL framework (e.g., MAPPO, QMIX). Train both individual dogfighting skills and team coordination. The hierarchical approach (team commander + individual pilots) from GTRI's ADT work is relevant.

#### Gap 5: Training Infrastructure (MEDIUM)

**Current**: Unknown (DCS World is not designed for headless mass simulation).
**Required**: Billions of training iterations (Heron Systems used 4B+ for ADT). Requires headless, parallelizable sim.

**Impact**: RL training requires running thousands of concurrent simulation instances. DCS World cannot do this. JSBSim can run headless at many times real-time.

**Remediation**: JSBSim for training (headless, parallelizable). Invest in GPU compute for RL training (cloud or local). DCS World only for human-readable validation.

#### Gap 6: DoD Qualification Standards (LOW-MEDIUM for now)

**Current**: No DoD qualification framework applied.
**Required**: AI Fight Club evaluates against DOW standards.

**Impact**: Unknown until Participant Guide is released. May require specific safety, reliability, or explainability properties.

**Remediation**: Monitor AI Fight Club Participant Guide release. The rule-based TDE's explainability is actually an advantage here -- hybrid architectures (RL + safety guardrails) may be required.

### What VigilAI Has That Others Don't

| Advantage | Value |
|-----------|-------|
| Physics-based sensor modeling | Most RL research uses perfect information; realistic sensors add fidelity |
| 108-test suite | Strong engineering discipline; most research teams have minimal testing |
| Domain expertise in wingman tactics | Tactical knowledge can inform reward shaping for RL training |
| DCS World integration | Useful for visualization, validation, and demo purposes |
| Rule-based TDE | Can serve as expert prior, safety layer, or reward shaping basis |

---

## 7. Recommendations

### Immediate (0-3 months)

1. **Register interest with AI Fight Club** -- Email ai.fight.club.lm@lmco.com immediately. Get on the list. Obtain the Participant Guide as soon as available.

2. **Stand up JSBSim + Gymnasium environment** -- Port the F-16 (or equivalent 4th-gen) model to JSBSim. Wrap in Gymnasium interface. This is table stakes for any competition entry.

3. **Prototype RL agent** -- Use Stable-Baselines3 (PPO) with the JSBSim environment. Start with 1v1 WVR to validate the pipeline. The LAG (https://github.com/liuqh16/LAG) and BVR Gym repositories provide reference implementations.

### Short-Term (3-6 months)

4. **Implement hierarchical RL** -- High-level tactical selector + low-level maneuver policies. Use the existing TDE knowledge to define the policy hierarchy and reward functions.

5. **Scale to 4v4 MARL** -- Implement multi-agent training (MAPPO or similar). This is the AI Fight Club format.

6. **Invest in training compute** -- Budget for cloud GPU instances. Competitive RL training requires significant compute (hundreds of GPU-hours minimum).

### Medium-Term (6-12 months)

7. **Develop LM sim adapter** -- When the AI Fight Club Participant Guide is released, build an adapter layer between your trained policies and the LM sim interface. If the API is Python-based, this should be straightforward.

8. **Hybrid architecture** -- Combine RL policies (for combat performance) with rule-based safety guardrails (for DoD qualification). This is likely what DoD actually wants -- performance + explainability.

9. **Publish results** -- AI Fight Club allows publication. Publishing builds credibility and attracts collaborators.

### Strategic Considerations

- **Shield AI is the company to beat** -- $5.6B valuation, Heron Systems heritage (ADT winner), Hivemind flying real aircraft, CCA program. They set the bar.
- **Anduril is the dark horse** -- Lattice OS, Fury drone with fighter designation, massive funding. Not primarily an AI dogfight competitor but their autonomy stack is formidable.
- **The real prize isn't the trophy** -- AI Fight Club is a supplier qualification pipeline for Lockheed Martin ($70B+ in annual revenue, 60% to suppliers). Performing well opens vendor relationships.
- **DCS World is a dead end for competition** -- No competition or government program uses it. Keep it for demos and visualization only.
- **The RL transition is non-optional** -- Every data point from DARPA ADT, ACE, and the broader research landscape says rule-based systems lose to learned policies in air combat. The question is not whether to adopt RL, but how fast.

---

## Sources

### Lockheed Martin AI Fight Club
- [AI Fight Club Official Page](https://www.lockheedmartin.com/en-us/capabilities/artificial-intelligence-machine-learning/ai-fight-club.html)
- [LM Press Release (June 3, 2025)](https://news.lockheedmartin.com/2025-06-03-Lockheed-Martins-AI-Fight-Club-TM-Puts-AI-to-the-Test-for-National-Security)
- [SpaceNews Coverage](https://spacenews.com/lockheed-martin-launches-ai-fight-club-to-test-algorithms-for-warfare/)
- [Defense Daily Coverage](https://www.defensedaily.com/lockheed-martin-unveils-all-comers-fight-club-to-test-out-ai-models-in-virtual-arena/advanced-transformational-technology/)
- [Military Embedded Systems](https://militaryembedded.com/ai/deep-learning/lockheed-martin-launches-ai-fight-club)

### DARPA AlphaDogfight Trials
- [DARPA ADT Announcement](https://www.darpa.mil/news/2020/alphadogfight-trial)
- [Wikipedia: DARPA AlphaDogfight](https://en.wikipedia.org/wiki/DARPA_AlphaDogfight)
- [Defense Daily: Heron Systems Wins](https://www.defensedaily.com/heron-systems-wins-crown-darpa-alphadogfight-trials/advanced-transformational-technology/)
- [Breaking Defense: AI Slays Top Pilot](https://breakingdefense.com/2020/08/ai-slays-top-f-16-pilot-in-darpa-dogfight-simulation/)
- [GTRI Lessons Learned](https://www.gtri.gatech.edu/newsroom/gtris-lessons-learned-2020-alphadogfight-trials)
- [Hierarchical RL for Air Combat (IEEE)](https://ieeexplore.ieee.org/document/9950612/)

### DARPA ACE Program
- [DARPA ACE Program Page](https://www.darpa.mil/research/programs/air-combat-evolution)
- [ACE: World First for AI in Aerospace (2024)](https://www.darpa.mil/news/2024/ace-ai-aerospace)
- [ACE Sim-to-Live Transition (2023)](https://www.darpa.mil/news/2023/ace-program-transition)
- [LM Missile-Evasion AI on X-62 VISTA (Feb 2026)](https://theaviationist.com/2026/02/25/lockheed-martin-tests-missile-evasion-ai-on-x-62-vista/)
- [Defense News: AI-Flown Fighter Dogfights (2024)](https://www.defensenews.com/air/2024/04/19/us-air-force-stages-dogfights-with-ai-flown-fighter-jet/)
- [EpiSci DARPA ACE Contract](https://www.airframer.com/news_story.html?release=91902)

### Competitive Landscape
- [Shield AI: $240M at $5.3B Valuation](https://shield.ai/shield-ai-raises-240m-at-5-3b-valuation-to-scale-hivemind-enterprise-an-ai-powered-autonomy-developer-platform/)
- [Shield AI Acquires Heron Systems](https://shield.ai/shield-ai-acquires-heron-systems/)
- [Shield AI Wikipedia](https://en.wikipedia.org/wiki/Shield_AI)
- [Anduril Fury First Flight](https://dronexl.co/2025/10/31/anduril-yfq-44a-autonomous-fighter-drone-first-flight/)
- [Anduril Fury Fighter Designation (Feb 2026)](https://robohorizon.com/en-us/news/2026/02/andurils-fury-drone-earns-fighter-jet-title-from-us-air-force/)
- [Collins Aerospace Sidekick CCA Software](https://www.prnewswire.com/news-releases/rtxs-collins-aerospace-autonomy-solution-sidekick-flies-ga-asis-yfq-42a-cca-platform-302693016.html)
- [Air Force CCA Mission Autonomy](https://defensescoop.com/2026/02/12/air-force-testing-mission-autonomy-package-cca-drone-prototypes/)

### Simulation Frameworks
- [JSBSim GitHub](https://github.com/JSBSim-Team/jsbsim)
- [LAG: Close Air Combat Environment (JSBSim+Gym)](https://github.com/liuqh16/LAG)
- [BVR Gym (arXiv)](https://arxiv.org/abs/2403.17533)
- [Tunnel: F-16 RL Training Environment (arXiv)](https://arxiv.org/html/2505.01953v1)
- [Harfang 3D Dogfight Sandbox](https://github.com/harfang3d/dogfight-sandbox-hg2)
- [AFSIM Overview (DSIAC)](https://dsiac.dtic.mil/models/afsim/)

### Academic / Government Research
- [DAF-MIT AI Accelerator](https://aia.mit.edu/)
- [AFRL Challenge Competition](https://www.griffissinstitute.org/challenge-competition/)
- [Air Force AI Doctrine Note 25-1 (April 2025)](https://www.doctrine.af.mil/Portals/61/documents/AFDN_25-1/AFDN%2025-1%20Artificial%20Intelligence.pdf)
