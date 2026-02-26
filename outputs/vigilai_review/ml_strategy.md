# VigilAI ML Strategy Assessment

**Date**: 2026-02-26
**Scope**: Evaluate whether VigilAI's rule-based TDE can compete against RL-trained agents, and recommend an ML integration path for competition entry (Lockheed Martin AI Fight Club Q1 2026 or similar).

---

## 1. Rule-Based vs ML Assessment

### Honest Verdict: The TDE Cannot Win Against RL-Trained Agents

VigilAI's Tactical Decision Engine is well-structured engineering. It has multi-sensor fusion, Pk-based weapon selection, survivability-driven abort logic, and a 5-state combat state machine. For a DCS World mod product, it is excellent. For competition against RL-trained agents, it will lose.

Here is why:

**The TDE is a hand-tuned heuristic system.** Every decision boundary is a hard-coded threshold:
- Survival threshold: 25% (hardcoded in CONFIG)
- Threat weights: DISTANCE=0.3, CAPABILITY=0.4, INTENT=0.2, ANGLE=0.1 (static)
- Evasive maneuver selection: if-else chain based on threat type and range bands
- Weapon selection: linear scoring function with fixed coefficients
- Combat state transitions: threshold-based (survival < 0.25 = EMERGENCY, < 0.6 = DEFENSIVE)

**What this means in practice:**
- The agent cannot discover novel tactics. It will always notch against a SAM at >20km, always terrain-mask at <20km. An RL agent that has trained against millions of variations will find the edge cases these rules miss.
- The agent cannot adapt mid-fight. The weights and thresholds are static. An RL agent continuously re-evaluates its policy against the actual state.
- The evasive maneuvers are template-based (defensive_turn, notching, defensive_spiral, terrain_masking, energy_management) with fixed parameters. An RL agent controls continuous surfaces and can generate maneuvers that no human expert would codify.
- The threat prioritization uses a weighted sum formula. RL agents learn implicit priority functions that capture non-linear interactions between range, aspect, closure rate, weapon state, and energy state simultaneously.

**Historical evidence is definitive.** In the 2020 DARPA AlphaDogfight Trials, every rule-based and scripted approach was eliminated in early rounds. Heron Systems' Falco (deep RL, PPO, ~4 billion training episodes) beat a human F-16 pilot 5-0 in the finals. The RL agents demonstrated:
- Superhuman gun tracking precision
- Novel energy management strategies no human pilot had codified
- Ability to exploit opponent patterns in real-time
- Continuous control at 10Hz that produced smooth, effective maneuvers

**The gap is structural, not incremental.** Adding more rules or tuning thresholds will not close it. The TDE's decision space is a finite set of if-else paths. An RL agent's policy network maps the full continuous state space to continuous actions, discovering strategies the rule designer never imagined.

### What the TDE Does Well (and Should Be Preserved)

The TDE has genuine value that should not be discarded:

1. **Domain knowledge is encoded correctly.** The sensor models (APG-68/77/81 radar equations, IRST thermal contrast, environmental factors) are physics-grounded. This is hard-won domain expertise.
2. **Safety constraints are explicit.** The abort logic, fuel reserves, weapon authorization checks, and engagement limits are operationally sound.
3. **The combat state machine is a valid structure.** PASSIVE/DEFENSIVE/OFFENSIVE/EMERGENCY/ABORT is a reasonable high-level decomposition.
4. **Weapon selection logic captures real engagement envelopes.** The weapon database with range bands, Pk calculations, aspect angle limits, and altitude constraints reflects real employment doctrine.

The right strategy is not to replace this -- it is to use it as a foundation.

---

## 2. State of the Art: What Are the Best Autonomous Air Combat AI Systems Using Today?

### Top-Tier Systems (2024-2026)

**Shield AI / Heron Systems (Falco -> Hivemind)**
- Acquired by Shield AI in 2021 for their RL capabilities
- Architecture: Multi-agent deep RL with PPO (Proximal Policy Optimization)
- Training: ~4 billion simulated dogfights against a league of 102 unique AI agents over 5 weeks
- Control: 10Hz continuous control (notably slower than competitors at 50Hz -- smoothness was key)
- Training paradigm: AlphaStar-style competitive league with diverse opponent policies
- Now deployed as "Hivemind" on V-BAT drones with Nvidia GPU modules
- Represents the gold standard for autonomous air combat AI

**DARPA ACE (Air Combat Evolution) Program**
- Follow-on to AlphaDogfight Trials
- Goal: human trust in AI-piloted combat aircraft
- Multiple performers (including Shield AI, Lockheed Martin Skunk Works, EpiSci)
- Progressing from simulation to live flight tests on modified L-39 aircraft

**Academic/Research State of the Art**
- **Hierarchical RL** (HRL): High-level policy selector + specialized low-level maneuver policies. Dominant approach in recent literature.
- **Model-Based Constrained RL**: Dreamer framework + safety-aware objectives + population-based self-play. Addresses the sim-to-real gap.
- **H3E Framework**: Three-level hierarchy embedding expert knowledge with a "Rule-Imitation-Reinforcement" (RIR) training paradigm. Directly relevant to VigilAI's hybrid path.
- **Graph Neural Networks + RL**: For multi-agent scenarios with variable numbers of friendlies/hostiles.

### Key Training Environments

| Environment | Fidelity | Focus | Status |
|-------------|----------|-------|--------|
| **JSBSim** (via Gymnasium) | High (6-DOF flight dynamics) | WVR and BVR | Open-source, actively maintained |
| **BVR Gym** | High (JSBSim-based, F-16 model) | BVR engagements | Open-source, includes missile models |
| **CloseAirCombat / LAG** | High (JSBSim-based) | 1v1 WVR dogfight | Open-source, self-play support |
| **Tunnel** | High (F-16 non-linear dynamics) | Aircraft control fundamentals | Open-source, Gymnasium-compatible |
| **DCS World** (via Lua scripting) | Very High (full sim fidelity) | Full mission scenarios | Proprietary, slow for training |

### Algorithms in Use

| Algorithm | Use Case | Notable Users |
|-----------|----------|---------------|
| **PPO** (Proximal Policy Optimization) | Primary policy training | Heron/Shield AI (Falco) |
| **SAC** (Soft Actor-Critic) | Continuous control, WVR | Multiple academic groups |
| **Dreamer v3** (Model-Based) | Sample-efficient training | Cutting-edge research |
| **MADDPG / QMIX** | Multi-agent cooperative | Team combat scenarios |
| **Behavioral Cloning + RL** | Hybrid imitation-then-RL | H3E, IN-RIL framework |

---

## 3. ML Integration Options

### Option A: Hybrid -- RL Layer on Top of Existing TDE (RECOMMENDED)

**Concept**: Use the TDE as an expert policy for imitation learning, then fine-tune with RL self-play.

**Architecture**:
```
[Observation Space] -> [Neural Network Policy] -> [Action Space]
                              |
                    Pre-trained via imitation
                    of TDE expert demonstrations
                              |
                    Fine-tuned via PPO self-play
                    against TDE + other RL agents
```

**Implementation Steps**:

1. **Environment Wrapper** (2-3 weeks)
   - Build a Gymnasium-compatible wrapper around JSBSim (use existing gym-jsbsim or BVR Gym as starting point)
   - Define observation space: own position/velocity/attitude, fuel, weapons state, detected contacts (position, type, range, bearing, closure rate), threat level
   - Define action space: heading change, altitude change, throttle, weapon release, countermeasure deploy, formation commands
   - The wrapper does NOT need DCS -- JSBSim provides the flight dynamics

2. **Expert Data Collection** (1 week)
   - Run the TDE against scripted opponents in JSBSim environment
   - Record (observation, action) pairs: ~100K-500K transitions
   - The TDE's decision logic maps directly: given sensor inputs, it produces engagement/evasion/formation decisions
   - This is the existing codebase's value -- it generates reasonable expert demonstrations

3. **Imitation Learning Phase** (1-2 weeks)
   - Train a neural network policy via behavioral cloning on TDE demonstrations
   - Architecture: MLP or LSTM (for temporal context), ~256-512 hidden units, 2-3 layers
   - Goal: the neural network reproduces TDE behavior with ~90% fidelity
   - This gives a warm start -- the RL phase does not need to learn from scratch

4. **RL Fine-Tuning Phase** (3-4 weeks)
   - PPO training with the imitation-learned policy as initialization
   - Self-play: the agent trains against copies of itself + the original TDE
   - Reward shaping: survival bonus, kill reward, fuel efficiency, mission completion
   - This is where the agent surpasses the TDE -- it discovers tactics the rules miss
   - Use the H3E-style "Rule-Imitation-Reinforcement" paradigm with adjustable expert-guidance loss

5. **Safety Constraints** (integrated throughout)
   - Keep the TDE's abort logic as a hard override (survival < 25% = disengage, not negotiable)
   - Weapon authorization remains gated by rules
   - The RL policy handles tactical decisions; the rules handle safety constraints

**Pros**:
- Leverages all existing domain knowledge
- Faster convergence (warm start from TDE demonstrations)
- Safety constraints preserved as hard overrides
- Academically validated approach (H3E, IN-RIL frameworks)
- Can deploy incrementally -- TDE remains fallback

**Cons**:
- Performance ceiling may be limited by TDE's observation/action space design
- Requires careful reward engineering
- Two systems to maintain (rule engine + neural policy)

**Timeline**: 8-12 weeks to first competitive agent

---

### Option B: Full ML -- Train from Scratch

**Concept**: Pure end-to-end RL, no TDE dependency. Train an agent from random initialization using self-play.

**Architecture**:
```
[Raw Observation Space] -> [Deep Neural Network] -> [Continuous Control Actions]
                                                         |
                                            Heading, altitude, throttle,
                                            weapon release, countermeasures
```

**Implementation**:
- Use JSBSim + BVR Gym as the base environment
- PPO or SAC with population-based self-play (AlphaStar league approach)
- 3-layer MLP or LSTM, ~512-1024 hidden units
- Train for 1B+ episodes (Heron trained for 4B)
- Requires significant compute: 4-8 GPUs training for 2-4 weeks minimum

**Pros**:
- Highest performance ceiling -- no human-designed limitations
- Cleaner architecture (single policy, no rule fallback)
- Can discover strategies humans never codified

**Cons**:
- Requires massive compute (thousands of GPU-hours)
- Long training time with uncertain convergence
- All domain knowledge in the TDE is thrown away
- Safety constraints must be learned, not guaranteed
- Heron Systems had a team of ML engineers and 5 weeks of intensive training -- this is not a solo effort

**Timeline**: 16-24 weeks minimum, high uncertainty

---

### Option C: TDE as Training Opponent

**Concept**: Keep the TDE as-is in DCS World. Build a separate ML agent in JSBSim that trains against a port of the TDE logic.

**Architecture**:
```
[JSBSim Environment]
    |
    +-- ML Agent (PPO policy, training)
    |
    +-- TDE Bot (ported Lua logic, opponent)
    |
    +-- Other ML Agents (self-play league)
```

**Implementation**:
- Port TDE decision logic to Python (or call Lua from Python)
- ML agent trains against TDE as one of many opponents in a league
- TDE provides a "curriculum" -- a baseline opponent that is better than random
- Gradually introduce harder opponents (copies of the learning agent)

**Pros**:
- TDE serves as a useful training curriculum opponent
- ML agent is not constrained by TDE's limitations
- Can still use the TDE in DCS while the ML agent trains separately

**Cons**:
- Requires porting TDE to Python (or building a Lua bridge)
- Two completely separate systems with no integration benefit
- The ML agent still needs the full training pipeline from Option B
- Does not leverage TDE knowledge efficiently (only as opponent, not as initialization)

**Timeline**: 14-20 weeks

---

## 4. Technology Recommendations

### Frameworks

| Component | Recommendation | Rationale |
|-----------|---------------|-----------|
| **RL Library** | Stable-Baselines3 (SB3) | PyTorch-based, well-documented, PPO/SAC implemented, 95% test coverage. Easier for a solo developer than RLlib. |
| **Simulation** | JSBSim + BVR Gym | High-fidelity F-16 flight dynamics, Gymnasium-compatible, open-source, purpose-built for air combat RL. |
| **Alternative Sim** | CloseAirCombat (LAG) | JSBSim-based, 1v1 WVR focus, self-play built in. Good for WVR training. |
| **Neural Net Framework** | PyTorch | SB3 is built on it. Better debugging and research flexibility than TensorFlow. |
| **Experiment Tracking** | Weights & Biases (free tier) | Track training runs, hyperparameters, reward curves. Essential for solo developer. |
| **Environment Wrapper** | Gymnasium (OpenAI Gym successor) | Standard interface, SB3-compatible, community support. |

### GPU Requirements

| Approach | Minimum Hardware | Recommended | Cloud Alternative |
|----------|-----------------|-------------|-------------------|
| **Option A (Hybrid)** | 1x RTX 3080 (10GB) | 1x RTX 4090 (24GB) | 1x A100 on Lambda/Vast.ai (~$1-2/hr) |
| **Option B (Full)** | 4x RTX 3080 | 4-8x A100 (cluster) | Multi-GPU cloud instance (~$8-20/hr) |
| **Option C (Opponent)** | 2x RTX 3080 | 2x RTX 4090 | 2x A100 (~$2-4/hr) |

**Key insight**: JSBSim runs on CPU. The GPU is for neural network training only. The simulation itself is lightweight. This means you can parallelize many environment instances on CPU while training the network on GPU. Heron Systems ran their simulation environments on CPUs with GPU for the neural network updates.

**For a solo developer on the HP ProBook (i7-1355U, no discrete GPU)**: You will need cloud compute. The CPU can run JSBSim environments, but RL training without a GPU is impractical for competitive results. Budget ~$200-500 for cloud GPU time for Option A.

### Software Stack

```
Python 3.11+
  |-- stable-baselines3 (PPO, SAC implementations)
  |-- gymnasium (environment interface)
  |-- jsbsim (flight dynamics)
  |-- torch (PyTorch for neural networks)
  |-- tensorboard / wandb (experiment tracking)
  |-- numpy, scipy (numerical computing)
  |-- py_trees (behavior trees, if needed for hybrid approach)
```

---

## 5. Timeline Estimate

### Option A (Recommended): Hybrid TDE + RL

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| **1. Environment Setup** | 2-3 weeks | JSBSim Gymnasium wrapper with VigilAI-compatible observation/action spaces |
| **2. Expert Data Collection** | 1 week | 100K+ TDE demonstration trajectories in JSBSim |
| **3. Imitation Learning** | 1-2 weeks | Neural policy that replicates TDE behavior (~90% fidelity) |
| **4. RL Fine-Tuning (Initial)** | 2-3 weeks | PPO agent that beats TDE consistently in 1v1 |
| **5. Self-Play League** | 2-3 weeks | Agent trained against diverse opponents, robust to varied tactics |
| **6. Competition Integration** | 1-2 weeks | Package for AI Fight Club submission format |
| **Buffer** | 1-2 weeks | Debugging, hyperparameter tuning, unexpected issues |
| **Total** | **10-16 weeks** | Competition-ready ML agent |

### Critical Path Dependencies

1. Environment wrapper must be solid before anything else works
2. Imitation learning validates the observation/action space design
3. RL training requires GPU access (cloud or hardware acquisition)
4. Competition format/API must be known to build the integration layer

---

## 6. Risk Assessment: Can This Be Done for Q1 2026?

### The Short Answer: It Is Very Tight

Today is 2026-02-26. Q1 2026 ends March 31, 2026. That gives approximately **5 weeks**.

Lockheed Martin's AI Fight Club was announced for Q1 2026 competition, with the simulation environment completing Q3 2025. Assuming the competition is late Q1 (March), you have about 4-5 weeks.

### Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Not enough time for full Option A** | HIGH | HIGH | Scope down to Minimum Viable ML (see Section 7) |
| **Competition format unknown/incompatible** | MEDIUM | HIGH | Contact LM immediately (AI.Fight.Club.LM@lmco.com), build to generic JSBSim interface |
| **GPU access delays** | LOW | MEDIUM | Pre-provision cloud GPU now (Lambda, Vast.ai, RunPod) |
| **RL training does not converge** | MEDIUM | HIGH | Start with behavioral cloning only -- even without RL fine-tuning, a neural policy cloned from TDE is a viable baseline |
| **Solo developer bandwidth** | HIGH | HIGH | AI assistance (Claude Code) can accelerate the Python implementation significantly |
| **JSBSim environment bugs** | MEDIUM | MEDIUM | Use existing BVR Gym or CloseAirCombat as starting points rather than building from scratch |
| **Reward function engineering** | MEDIUM | MEDIUM | Start simple (survival + kills), iterate based on observed behavior |

### Realistic Assessment

**For AI Fight Club Q1 2026 specifically**: You are almost certainly too late for the first competition round if it happens in March. The minimum path (Section 7) requires 4-6 weeks even with aggressive AI-assisted development.

**For a subsequent competition or demonstration**: 10-16 weeks (Option A full) is achievable for one developer + AI assistance, targeting Q2-Q3 2026.

**What you CAN do in 5 weeks**: Build the environment wrapper, collect expert demonstrations, and train a behavioral cloning agent. This gives you a neural policy that mimics the TDE -- not groundbreaking, but it proves the pipeline works and positions you for RL fine-tuning immediately after.

---

## 7. Minimum Viable ML: The Smallest ML Addition That Adds Competitive Value

### Approach: Learned Threat Prioritization via Behavioral Cloning

The single highest-value ML addition to VigilAI requires no RL training at all.

**What**: Replace the TDE's hand-tuned threat prioritization formula with a small neural network trained on expert engagements.

**Current TDE threat prioritization** (from `tactical_decision_engine.lua`):
```lua
local priority = (distanceFactor * 0.3) +
                (capabilityFactor * 0.4) +
                (intentFactor * 0.2) +
                (angleFactor * 0.1)
```

This is a linear weighted sum. It cannot capture interactions (e.g., a low-capability threat at close range with high closure rate is more dangerous than the sum of its parts suggests).

**Replacement**: A 2-layer MLP (64 hidden units) that takes [distance, capability, intent, angle, closure_rate, aspect_angle, altitude_diff, weapon_state, fuel_state] and outputs a threat priority score. Train it on recorded engagements from DCS where the TDE's decisions were correct (positive examples) and where they led to losses (negative examples with corrected priorities).

**Implementation**:
1. Record 1000+ engagement scenarios in DCS with the TDE
2. Label outcomes (kill, loss, survived, aborted)
3. Train a small neural network to predict optimal priority ordering based on outcomes
4. Export the trained network to ONNX format
5. Call from Lua via a lightweight ONNX runtime (or a simple socket to a Python process)

**Timeline**: 2-3 weeks
**GPU Required**: None -- this trains on CPU in minutes
**Competitive Value**: Marginal improvement in threat assessment accuracy, but more importantly, it proves the ML integration pipeline and creates the foundation for larger ML additions.

### Next Step Up: Learned Evasive Maneuvering

The second highest-value addition: replace the template-based evasive maneuver selection with a learned policy.

**Current system** (from `survivability.lua`):
```lua
if primaryThreat.type == "sam" then
    if primaryThreat.range > 20000 then
        return EVASIVE_MANEUVERS.notching
    else
        return EVASIVE_MANEUVERS.terrain_masking
    end
elseif primaryThreat.type == "fighter" then
    ...
```

This selects from 5 fixed templates. A learned policy could output continuous maneuver parameters (bank angle, pull-up rate, roll direction, duration) conditioned on the full threat picture.

**This is where the RL payoff starts.** Train via:
1. Imitation learning from the TDE's maneuver selections (warm start)
2. RL fine-tuning in JSBSim against missile threats
3. Reward: survival probability increase after maneuver

**Timeline**: 4-6 weeks (requires JSBSim environment wrapper)
**GPU Required**: Yes (1x consumer GPU sufficient)
**Competitive Value**: Significant -- evasive maneuvering is where RL agents dramatically outperform rule-based systems.

---

## Summary Recommendation

| Priority | Action | Timeline | Effort |
|----------|--------|----------|--------|
| **1 (Now)** | Contact Lockheed Martin about AI Fight Club timeline and format | This week | 1 hour |
| **2 (Immediate)** | Build JSBSim Gymnasium wrapper using BVR Gym as starting point | 2-3 weeks | Solo + AI assist |
| **3 (Parallel)** | Implement Minimum Viable ML (learned threat prioritization) | 2-3 weeks | Solo + AI assist |
| **4 (Next)** | Collect TDE expert demonstrations in JSBSim environment | 1 week | Automated |
| **5 (Core)** | Behavioral cloning of full TDE policy | 1-2 weeks | Solo + GPU |
| **6 (Payoff)** | PPO fine-tuning with self-play | 3-4 weeks | Solo + cloud GPU |
| **7 (Competition)** | Package for competition submission format | 1-2 weeks | Solo + AI assist |

**The bottom line**: VigilAI's TDE is a strong product for DCS World. It is not competitive against RL-trained agents. The hybrid path (Option A) is the right strategy -- it preserves the domain knowledge in the TDE while adding the adaptive capability that RL provides. For one developer with AI assistance, a competition-viable agent is achievable in Q2-Q3 2026. Q1 2026 is too tight for a full RL agent, but you can build the pipeline and have a behavioral cloning baseline ready.

---

## Sources

### DARPA AlphaDogfight & Heron Systems
- [DARPA AlphaDogfight - Wikipedia](https://en.wikipedia.org/wiki/DARPA_AlphaDogfight)
- [Heron Systems - Alpha Dogfight Trials](https://heronsystems.com/work/alpha-dogfight-trials/)
- [Exclusive Interview: Heron Systems VP on AlphaDogfight Victory](https://www.overtdefense.com/2020/09/07/exclusive-interview-with-heron-systems-vice-president-on-their-ai-victory/)
- [Hierarchical RL for Air Combat at DARPA AlphaDogfight Trials (IEEE)](https://ieeexplore.ieee.org/document/9950612/)
- [Shield AI Acquires Heron Systems](https://shield.ai/shield-ai-acquires-heron-systems/)

### Lockheed Martin AI Fight Club
- [AI Fight Club - Lockheed Martin](https://www.lockheedmartin.com/en-us/capabilities/artificial-intelligence-machine-learning/ai-fight-club.html)
- [Lockheed Martin's AI Fight Club Puts AI to the Test (June 2025)](https://news.lockheedmartin.com/2025-06-03-Lockheed-Martins-AI-Fight-Club-TM-Puts-AI-to-the-Test-for-National-Security)

### Training Environments
- [BVR Gym: RL Environment for BVR Air Combat](https://arxiv.org/html/2403.17533)
- [BVR Gym GitHub](https://github.com/xcwoid/BVRGym)
- [CloseAirCombat (LAG) - JSBSim 1v1 Environment](https://github.com/liuqh16/LAG)
- [Tunnel: Training Environment for High Performance Aircraft RL](https://arxiv.org/html/2505.01953v1)
- [gym-jsbsim: RL Environment for Aircraft Control](https://github.com/Gor-Ren/gym-jsbsim)

### Hybrid Imitation + Reinforcement Learning
- [Imitative RL Framework for Autonomous Dogfight](https://arxiv.org/html/2406.11562v1)
- [H3E: Learning Air Combat with Hierarchical Framework Embedding Expert Knowledge](https://www.sciencedirect.com/science/article/abs/pii/S0957417423035868)
- [IN-RIL: Interleaved Reinforcement and Imitation Learning](https://arxiv.org/html/2505.10442v1)

### RL for Air Combat - State of the Art
- [DRL-based Air Combat Maneuver Decision-Making: Literature Review (Springer)](https://link.springer.com/article/10.1007/s10462-023-10620-2)
- [Hierarchical RL for Multi-UAV Air Combat (Nature)](https://www.nature.com/articles/s41598-024-54938-5)
- [Hierarchical Multi-Agent RL for Aerial Combat](https://arxiv.org/html/2505.08995v1)
- [Model-Based Constrained RL for Aerial Maneuver Games](https://www.preprints.org/manuscript/202510.2280)

### Frameworks
- [Stable-Baselines3 Documentation](https://stable-baselines3.readthedocs.io/)
- [Stable-Baselines3 GitHub](https://github.com/DLR-RM/stable-baselines3)
- [CleanRL: Single-file Deep RL Implementations](https://github.com/vwxyzjn/cleanrl)
