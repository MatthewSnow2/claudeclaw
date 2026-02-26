# Consolidated Assessment: VigilAI Autonomous Wingman

**Date**: 2026-02-26
**Reviewers**: Codebase Architect, Competition Intelligence Analyst, AI/ML Strategy Advisor, Implementation Planner, Devil's Advocate
**Project**: VigilAI DCS Wingman (v1.0 complete)
**Target**: Lockheed Martin AI Fight Club / Autonomous Air Combat Competition Entry

---

## Executive Summary

VigilAI is a genuinely impressive piece of work -- 8,248 LOC of Lua implementing physics-based radar models, a 5-state combat FSM, dynamic mission adaptation, and realistic sensor simulation. The codebase scores 7/10 on architecture with excellent DCS abstraction (only 3 minor API leaks). The core domain knowledge (threat prioritization, engagement logic, sensor modeling) is transferable and valuable.

However, all five specialists independently conclude that **VigilAI in its current form cannot compete in AI Fight Club**. Three structural gaps -- language (Lua vs Python), intelligence paradigm (rules vs RL), and scale (1-ship vs 4v4 multi-agent) -- require fundamental transformation, not incremental improvement. The Q1/Spring 2026 timeline is extremely tight.

The unanimous recommendation: **pursue a dual-track strategy** -- monetize the existing DCS mod immediately while building toward competition entry on a realistic timeline.

---

## Overall Assessment: CONDITIONAL GO

**Condition**: The "GO" is for the dual-track strategy below, NOT for rushing an AI Fight Club entry in the next few weeks.

---

## Cross-Referenced Findings

### Where All 5 Specialists Agree

| Finding | Codebase | Competition | ML Strategy | Impl. Plan | Devil's Advocate |
|---------|:--------:|:-----------:|:-----------:|:----------:|:----------------:|
| Rule-based TDE can't beat RL agents | -- | Yes | Yes | Yes | Yes (Fatal) |
| Core domain knowledge IS valuable | Yes (7/10) | Yes | Yes (reward shaping) | Yes (transferable) | Yes |
| Lua must become Python | Implied | Yes | Yes | Yes (~34h) | Yes (Fatal) |
| Q1 2026 is too tight | -- | Yes | Yes | Tight but possible | Yes (Fatal) |
| Ship DCS mod for revenue NOW | -- | -- | -- | -- | Yes |
| 4v4 multi-agent is required | -- | Yes | -- | Yes (~45h) | -- |

### Where Specialists Diverge

**Codebase Architect** rates DCS coupling at 8/10 (only 3 minor leaks) -- more optimistic than the Devil's Advocate who says "only 7-10% of code is reusable." The truth is nuanced: the DCS abstraction layer is clean, but the Lua-to-Python port means rewriting regardless. The LOGIC is transferable, the CODE is not.

**Implementation Planner** says 5 weeks / 206 hours is possible. **Devil's Advocate** says that's unrealistic for one person with no RL experience. The ML Strategy Advisor splits the difference: 10-16 weeks with hybrid approach. **Realistic timeline: 12 weeks (May-June 2026).**

### Critical Code Findings (Codebase Architect)

1. **Mutation bug**: `FormationController.setFormation()` at `formation_controller.lua:177-180` permanently corrupts the FORMATIONS table. Must fix before shipping DCS mod.
2. **TDE has zero tests**: The 442-LOC "brain" of the system has no test coverage. Critical gap.
3. **Voice recognition is entirely stub code**: Non-functional. Remove from marketing claims.
4. **`VigilAI.update()` is a 220-line god function**: Needs decomposition for maintainability.
5. **`calculateRange()`/`calculateBearing()` duplicated across 7-8 modules**: Extract to `math_utils.lua`.

---

## The Three Competitions

| Competition | Timeline | Format | Fit for M2AI | Action |
|------------|----------|--------|:------------:|--------|
| **LM AI Fight Club** | Spring 2026 (imminent) | 4v4, LM proprietary sim, may need DOW clearance | Medium | Email ai.fight.club.lm@lmco.com TODAY to confirm timeline and requirements |
| **Anduril AI Grand Prix** | May-July 2026 qualifiers | Vision-based drone racing, Python, open to individuals, $500K prizes | High | Register at theaigrandprix.com |
| **BVR Gym / Academic** | Open-ended | BVR air combat, Python/JSBSim, publish paper | High | Build agent, publish, build portfolio |

---

## Recommended Dual-Track Strategy

### Track A: Monetize Now (This Week)
1. **Fix the formation mutation bug** (1 hour)
2. **Ship VigilAI v1.0 on Gumroad** as a premium DCS World mod (1-2 days)
3. Price: $19.99 (premium mod market)
4. Add tests for TDE (high priority, 2-3 hours)
5. This generates revenue and validates market demand independently of any competition

### Track B: Competition Pipeline (12 Weeks)

**Week 1: Intelligence & Registration**
- Email ai.fight.club.lm@lmco.com to confirm AIFC1 timeline, format, and registration status
- Register for Anduril AI Grand Prix (if open)
- Set up JSBSim + Gymnasium + Python environment locally

**Weeks 2-3: Python Port of Core Logic**
- Port TDE threat prioritization, combat FSM, and sensor models to Python (~34 hours)
- Create simulation-agnostic interface (state space / action space abstraction)
- Test against JSBSim or BVR Gym baseline opponents
- This produces a standalone Python air combat decision engine regardless of competition outcome

**Weeks 4-6: RL Foundation**
- Implement behavioral cloning: train neural network to mimic TDE decisions
- This is the "minimum viable ML" -- proves the pipeline, requires no GPU
- Set up PPO training loop with self-play
- Begin RL fine-tuning (cloud GPU, $200-500 budget)
- Target: RL agent that matches TDE performance

**Weeks 7-9: Multi-Agent & Competition-Specific**
- Extend from 1-ship to 4-ship team coordination
- Adapt to competition-specific simulation environment (once known)
- Implement communication protocol between agents

**Weeks 10-12: Optimization & Submission**
- Performance tuning against diverse opponents
- Documentation and submission preparation
- Demo video / presentation

### Decision Gates

| Week | Gate | Go Criteria | Pivot If |
|------|------|-------------|----------|
| 1 | Competition Access | Can register, timeline > 8 weeks out | Target Anduril AI Grand Prix instead |
| 3 | Python Port | Core logic runs in Python, beats scripted opponents | Publish as open-source portfolio piece |
| 6 | RL Baseline | RL agent matches TDE performance | Stay rule-based, compete in format that allows it |
| 9 | Multi-Agent | 4-ship coordination works | Enter as single-agent if competition allows |

---

## Resource Requirements

| Resource | Cost | When Needed |
|----------|------|-------------|
| Cloud GPU (RL training) | $200-500 | Weeks 4-12 |
| JSBSim + BVR Gym (open source) | Free | Week 1 |
| Gumroad account (DCS mod sales) | Free (10% commission) | This week |
| AI Fight Club registration | Free (email) | Today |
| Anduril AI Grand Prix registration | TBD | This week |

---

## Kill Criteria

Stop pursuing the competition track if:

1. **Week 1**: AI Fight Club requires DOW clearance or defense contractor status that M2AI cannot obtain
2. **Week 3**: Python port reveals the TDE logic is too tightly coupled to DCS physics to be portable
3. **Week 6**: RL training produces no improvement over random policy after 48 hours of compute
4. **Any time**: Competition workload starts impacting M2AI consulting revenue or other pipeline items

---

## Immediate Actions (Tonight/Tomorrow)

1. **Email ai.fight.club.lm@lmco.com** -- Confirm AIFC1 timeline, registration status, and whether small companies/individuals can participate
2. **Check theaigrandprix.com** -- Verify Anduril AI Grand Prix registration is open
3. **Fix formation mutation bug** (`formation_controller.lua:177-180`) -- 30 minutes
4. **List VigilAI on Gumroad** -- Start generating revenue from the finished product
5. **Add TDE tests** -- The brain of the system has zero test coverage

---

## Files Produced

| File | Agent | Key Finding |
|------|-------|-------------|
| `codebase_architecture.md` | Codebase Architect | 7/10 architecture, mutation bug, TDE untested |
| `competition_intelligence.md` | Competition Intel | AI Fight Club 4v4, Spring 2026, Anduril as alternative |
| `ml_strategy.md` | ML Strategy | Hybrid RL on TDE, 10-16 weeks, JSBSim + PPO |
| `implementation_plan.md` | Implementation Planner | 206 hours / 5 weeks, 3 gaps to close |
| `devils_advocate.md` | Devil's Advocate | 3 fatal for AI Fight Club, ship DCS mod + Anduril |
| `consolidated_assessment.md` | Synthesis | This document |
