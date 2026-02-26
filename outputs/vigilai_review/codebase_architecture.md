# VigilAI DCS Wingman -- Codebase Architecture Review

**Reviewer**: Codebase Architect (Claude)
**Date**: 2026-02-26
**Version Reviewed**: 1.0.0-MVP
**Purpose**: Competition readiness assessment

---

## Table of Contents

1. [Architecture Assessment](#1-architecture-assessment)
2. [DCS Coupling Analysis](#2-dcs-coupling-analysis)
3. [Modularity Score](#3-modularity-score)
4. [Code Quality](#4-code-quality)
5. [Abstraction Layer Recommendations](#5-abstraction-layer-recommendations)
6. [Competitive Differentiator Analysis](#6-competitive-differentiator-analysis)
7. [LOC and Complexity Metrics](#7-loc-and-complexity-metrics)
8. [Test Coverage Assessment](#8-test-coverage-assessment)

---

## 1. Architecture Assessment

### Pattern: Hub-and-Spoke with Central Orchestrator

The project follows a hub-and-spoke topology. `main.lua` (640 LOC) serves as the single orchestrator, importing 13 modules at file scope (lines 9-21) and coordinating them through a 10Hz update loop (`VigilAI.update()`, line 201).

**Module layout** (16 source files across 8 directories):

```
vigilai/src/
  main.lua                          -- Orchestrator (640 LOC)
  core/
    tactical_decision_engine.lua    -- TDE: threat/weapon/survival AI (442 LOC)
    sensor_simulation.lua           -- Basic sensor fallback (182 LOC)
  combat/
    combat_manager.lua              -- 5-state combat FSM (518 LOC)
    weapon_system.lua               -- Weapon database + Pk calc (449 LOC)
    survivability.lua               -- Threat analysis + evasion (549 LOC)
  commands/
    command_processor.lua           -- Voice/text command dispatch (467 LOC)
  dcs/
    mission_integration.lua         -- DCS API abstraction layer (298 LOC)
  formation/
    formation_controller.lua        -- 6 formation types (305 LOC)
  mission/
    mission_manager.lua             -- Mission lifecycle (881 LOC)
    dynamic_objectives.lua          -- Runtime objective generation (610 LOC)
  sensors/
    advanced_sensor_simulation.lua  -- Physics-based multi-sensor (702 LOC)
  training/
    pilot_coach.lua                 -- Real-time coaching (631 LOC)
    training_scenarios.lua          -- 8 progressive scenarios (652 LOC)
  voice/
    voice_recognition.lua           -- STT integration stubs (245 LOC)
  security/
    license_manager.lua             -- Licensing + anti-tamper (677 LOC)
```

### Object Model: Inconsistent

The TDE (`tactical_decision_engine.lua`) is the **only** module using Lua metatables for OOP:

```lua
-- tactical_decision_engine.lua:32-48
function TacticalDecisionEngine:new()
    local tde = { ... }
    setmetatable(tde, self)
    self.__index = self
    return tde
end
```

All 15 other modules use the singleton-table pattern:

```lua
local Module = {}
function Module.init() ... end
function Module.update(...) ... end
return Module
```

This inconsistency means `main.lua` instantiates TDE (`VigilAI.tde = TacticalDecisionEngine:new()` at line 84) but calls all other modules as singletons (`CombatManager.init()`, `WeaponSystem.init()`, etc.). For a competition, this is a minor aesthetic issue, but it creates a real problem: singleton modules store all mutable state at the module table level, making parallel instantiation impossible and testing harder.

### Initialization Sequence

`VigilAI.init()` (lines 48-195) follows a strict order:

1. License validation (lines 61-78) -- hard gate, blocks all further init on failure
2. TDE instantiation (line 84)
3. MissionIntegration.init (line 88)
4. FormationController.init (line 96)
5. SensorSimulation.init (line 104)
6. AdvancedSensorSimulation.init (line 112)
7. CombatManager.init (line 120)
8. VoiceRecognition.init (line 128)
9. CommandProcessor.init (line 136)
10. PilotCoach.init (line 151)
11. TrainingScenarios.init (line 160)
12. MissionManager.init (line 169)
13. DynamicObjectives.init (line 178)
14. F10 menu registration (line 183)
15. Timer schedule for update loop (line 190)

Each init is gated by `VigilAI.systems[name] = true/false` flags. This is well-structured: partial initialization is handled gracefully, and the update loop checks these flags before calling each subsystem.

### Update Loop Architecture

The main update loop (`VigilAI.update()`, lines 201-420) follows this flow per tick:

1. License enforcement check (every 600 ticks, lines 207-215)
2. Get player and wingman unit states via `MissionIntegration.getUnitState()` (lines 222-240)
3. Scan contacts via `MissionIntegration.scanForContacts()` (line 248)
4. Run sensor simulation on contacts (lines 254-275)
5. Process contacts through TDE (lines 278-280)
6. Update CombatManager (lines 283-294)
7. Update PilotCoach (lines 297-306)
8. Update TrainingScenarios (lines 309-318)
9. Update MissionManager (lines 321-330)
10. Update DynamicObjectives (lines 333-342)
11. Evaluate survival probability (lines 345-380)
12. Update FormationController (lines 383-415)

### Architecture Verdict

**Strengths**: Clean hub-and-spoke, graceful partial initialization, systematic update ordering.

**Weaknesses**: Single-threaded monolithic update (all subsystems run every tick even when idle), missionContext rebuilt 5 times per tick (lines 285-342, see Section 4), TDE OOP inconsistency with rest of codebase.

**Rating**: 7/10 -- Solid for an MVP; needs optimization passes for production load.

---

## 2. DCS Coupling Analysis

### Primary Coupling Point: mission_integration.lua

The project correctly funnels nearly all DCS World API calls through a single abstraction layer: `mission_integration.lua` (298 LOC). This module wraps:

| DCS API | Wrapper Function | Line |
|---------|-----------------|------|
| `Unit.getByName()` | `MissionIntegration.getUnitState()` | 58 |
| `unit:getPosition()` | Attitude extraction (pitch/roll/yaw) | 88-91 |
| `unit:getVelocity()` | Velocity normalization | 83-86 |
| `unit:getFuel()` | Fuel state | 93 |
| `unit:getAmmo()` | Ammo inventory | 94 |
| `unit:getLife()` | Health status | 95 |
| `world.searchObjects()` | `MissionIntegration.scanForContacts()` | ~130 |
| `trigger.action.outTextForUnit()` | `MissionIntegration.sendMessageToPlayer()` | ~190 |
| `group:getController()` | Formation task commands | ~210 |
| `missionCommands.addCommandForCoalition()` | F10 menu registration | ~250 |
| `coalition.side` | Coalition constants | Throughout |

**Attitude extraction** (lines 88-91) is particularly noteworthy. It correctly derives Euler angles from the DCS position matrix:

```lua
attitude = {
    pitch = math.asin(position.x.y),
    roll = math.atan2(-position.z.y, position.y.y),
    yaw = math.atan2(position.x.z, position.x.x)
}
```

This is the mathematically correct decomposition for DCS's right-handed coordinate system.

### DCS Leaks (Coupling Violations)

Three locations bypass the MissionIntegration abstraction:

**Leak 1: sensor_simulation.lua line 40**
```lua
local current_time = DCS.getModelTime()
```
This directly calls `DCS.getModelTime()` instead of using `timer.getTime()` or a wrapped time function. This will crash outside DCS because `DCS` is a mission scripting environment global not available in all contexts.

**Leak 2: main.lua lines 222-223**
```lua
local playerUnit = Unit.getByName(CONFIG.PLAYER_UNIT_NAME)
local wingmanUnit = Unit.getByName(CONFIG.AI_WINGMAN_NAME)
```
`main.lua` calls `Unit.getByName()` directly and then passes the raw DCS unit objects to `MissionIntegration.getUnitState()`. This is partially justified (main.lua needs the Unit reference to pass it), but it means main.lua has a hard dependency on the `Unit` global.

**Leak 3: main.lua line 190**
```lua
timer.scheduleFunction(VigilAI.update, nil, timer.getTime() + updateInterval)
```
Direct use of `timer.scheduleFunction` and `timer.getTime()`. These are DCS-specific scheduling APIs.

### DCS Globals Used

The following DCS globals are referenced across the codebase:

| Global | Files Using It |
|--------|---------------|
| `Unit` | main.lua, mission_integration.lua |
| `timer` | main.lua, mission_integration.lua, voice_recognition.lua |
| `env` | 15 of 16 modules (logging) |
| `trigger` | mission_integration.lua |
| `world` | mission_integration.lua |
| `missionCommands` | mission_integration.lua |
| `coalition` | mission_integration.lua |
| `DCS` | sensor_simulation.lua |
| `lfs` | license_manager.lua |

### Coupling Verdict

**Score: 8/10** -- Excellent isolation for a DCS mod. The MissionIntegration abstraction layer is well-designed. The three leaks are minor and easily fixable. The `env` global usage across all modules is acceptable (it is the DCS logging API and would need a global replacement to fully abstract, which adds complexity for minimal benefit).

**Fix priority**:
1. **HIGH**: `sensor_simulation.lua:40` -- Replace `DCS.getModelTime()` with `timer.getTime()` for consistency and testability
2. **LOW**: `main.lua:222-223` -- Could wrap in `MissionIntegration.getUnit(name)` but marginal benefit
3. **LOW**: `main.lua:190` -- Timer scheduling is inherently DCS-specific; wrapping adds no value

---

## 3. Modularity Score

### Module Independence Matrix

| Module | Inbound Deps | Outbound Deps | Coupling Level |
|--------|-------------|---------------|---------------|
| main.lua | 0 | 13 | Hub (expected) |
| mission_integration.lua | 5 | 0 (DCS only) | Clean adapter |
| tactical_decision_engine.lua | 1 (main) | 0 | Isolated |
| combat_manager.lua | 1 (main) | 2 (weapon_system, survivability) | Domain cluster |
| weapon_system.lua | 2 | 0 | Leaf |
| survivability.lua | 2 | 0 | Leaf |
| command_processor.lua | 2 | 5 (lazy require) | High fan-out |
| formation_controller.lua | 2 | 0 | Leaf |
| sensor_simulation.lua | 1 | 0 | Leaf |
| advanced_sensor_simulation.lua | 1 | 0 | Leaf |
| mission_manager.lua | 1 | 0 | Leaf |
| dynamic_objectives.lua | 1 | 0 | Leaf |
| pilot_coach.lua | 1 | 0 | Leaf |
| training_scenarios.lua | 1 | 0 | Leaf |
| voice_recognition.lua | 1 | 1 (command_processor) | Thin bridge |
| license_manager.lua | 1 | 0 | Leaf |

### Positive Patterns

**1. Clean domain boundaries.** The combat cluster (combat_manager -> weapon_system, survivability) is well-structured. CombatManager orchestrates the two subsystems without them knowing about each other.

**2. Lazy loading in command_processor.lua.** Instead of hard imports, the command processor uses `require()` inside handler functions (e.g., line ~280: `local FormationController = require('vigilai.src.formation.formation_controller')`). This breaks circular dependencies and keeps the module loadable independently.

**3. No cross-domain coupling.** Training modules never import combat modules directly. Mission modules never import sensor modules. Everything flows through main.lua's update loop.

### Negative Patterns

**1. Utility function duplication (CRITICAL).**

`calculateRange()` is copy-pasted into 7 modules:

| Module | Function Location |
|--------|------------------|
| main.lua | `VigilAI.calculateRange()` line 530 |
| weapon_system.lua | `WeaponSystem.calculateRange()` line 413 |
| survivability.lua | `Survivability.calculateRange()` line 489 |
| combat_manager.lua | `CombatManager.calculateRange()` line 512 |
| sensor_simulation.lua | `SensorSimulation.calculateRange()` line 148 |
| advanced_sensor_simulation.lua | `AdvancedSensorSimulation.calculateRange()` line 658 |
| pilot_coach.lua | `PilotCoach.calculateRange()` line 625 |
| training_scenarios.lua | `TrainingScenarios.calculateRange()` line 646 |

`calculateBearing()` is duplicated in 6 modules (same list minus combat_manager.lua and training_scenarios.lua).

All implementations are identical: `math.sqrt(dx^2 + dy^2 + dz^2)`. This is a maintainability hazard. If the formula ever needs adjustment (e.g., for Earth curvature at long ranges), 7 files need synchronized edits.

**Recommendation**: Extract to `vigilai/src/core/math_utils.lua`:
```lua
local MathUtils = {}
function MathUtils.calculateRange(pos1, pos2) ... end
function MathUtils.calculateBearing(pos1, pos2) ... end
return MathUtils
```

**2. missionContext rebuilt 5 times per tick.**

In `main.lua` lines 285-342, the identical missionContext table is constructed 5 separate times:

```lua
-- Line 285 (for CombatManager)
local missionContext = {
    fuel = wingmanState.fuel,
    currentTime = currentTime,
    position = wingmanState.position,
    nearestThreat = VigilAI.findNearestThreat(detectedContacts, wingmanState.position)
}

-- Line 298 (for PilotCoach) -- IDENTICAL
-- Line 310 (for TrainingScenarios) -- IDENTICAL
-- Line 322 (for MissionManager) -- IDENTICAL
-- Line 334 (for DynamicObjectives) -- IDENTICAL
```

Each reconstruction also calls `VigilAI.findNearestThreat()`, which iterates through all contacts. At 10Hz with 50 contacts, that is 500 unnecessary iterations per second.

**Recommendation**: Build missionContext once before the subsystem update block:
```lua
local missionContext = {
    fuel = wingmanState.fuel,
    currentTime = currentTime,
    position = wingmanState.position,
    nearestThreat = VigilAI.findNearestThreat(detectedContacts, wingmanState.position)
}
```

**3. FormationController.setFormation() mutates shared table (BUG).**

`formation_controller.lua` lines 177-180:

```lua
local formation = FORMATIONS[formationType]
local scale = distance / math.sqrt(formation.offset.x^2 + formation.offset.z^2)
formation.offset.x = formation.offset.x * scale
formation.offset.z = formation.offset.z * scale
```

This modifies the `FORMATIONS` table's offset values in place. After calling `setFormation("line_abreast", 1000)`, the original `line_abreast` definition is permanently corrupted. Subsequent calls without a distance parameter will use the mutated offsets, and calling `setFormation("line_abreast", 500)` will scale from the already-scaled values, compounding the error.

**Recommendation**: Deep-copy the formation before mutating:
```lua
local formation = {
    offset = { x = FORMATIONS[formationType].offset.x, z = FORMATIONS[formationType].offset.z },
    tolerance = FORMATIONS[formationType].tolerance,
    description = FORMATIONS[formationType].description
}
```

### Modularity Score: 6.5/10

The domain separation is excellent, but the utility duplication and mutable-state bug bring the score down. These are all fixable in a single focused session.

---

## 4. Code Quality

### Documentation

**Module-level**: Every file has a header block comment describing purpose. Example from `tactical_decision_engine.lua`:
```lua
--[[
VigilAI Tactical Decision Engine (TDE)
Core AI decision-making system for DCS wingman operations

This module implements the central decision-making logic for VigilAI,
including threat analysis, weapon selection, formation control, and survivability.
]]--
```

**Function-level**: The TDE uses LDoc-style annotations (e.g., `@return table: TDE instance`). Other modules use plain `--` comments above functions. Coverage is inconsistent -- approximately 60% of public functions have descriptive comments.

**Inline comments**: Present throughout, especially in complex calculations (e.g., sensor_simulation.lua radar equation, survivability.lua closure rate). Quality is good where present.

### Error Handling

**Defensive nil checks**: Consistently applied. Most functions validate inputs before proceeding:

```lua
-- mission_manager.lua typical pattern
function MissionManager.update(playerState, wingmanState, contacts, combatStatus, missionContext)
    if not MissionManager.initialized then return false end
    if not playerState or not wingmanState then return false end
    ...
end
```

**pcall usage**: Absent. No functions use `pcall()` for error recovery. In DCS, an unhandled error in a `timer.scheduleFunction` callback kills the scheduled function permanently, meaning a single nil-access crash in the update loop would disable the entire mod until mission restart.

**Recommendation**: Wrap `VigilAI.update()` body in pcall:
```lua
function VigilAI.update()
    local success, err = pcall(VigilAI._updateInternal)
    if not success then
        env.error("VigilAI: Update error: " .. tostring(err))
    end
    return timer.getTime() + (1 / CONFIG.UPDATE_RATE)
end
```

### Naming Conventions

- **Modules**: PascalCase tables (`CombatManager`, `WeaponSystem`, `MissionIntegration`) -- consistent
- **Functions**: PascalCase methods on module tables (`CombatManager.update()`) -- consistent
- **Constants**: UPPER_SNAKE_CASE in local CONFIG tables -- consistent
- **Local variables**: camelCase -- consistent
- **One violation**: `_deltaTime` in main.lua:218 uses underscore prefix for "unused" variable, which is a Lua convention but inconsistent with the rest of the codebase

### Code Smells

**1. God function: `VigilAI.update()`** -- 220 lines (201-420) handling all subsystem orchestration. Should be decomposed into:
- `VigilAI.updateSensors()`
- `VigilAI.updateCombat()`
- `VigilAI.updateTraining()`
- `VigilAI.updateMission()`
- `VigilAI.updateFormation()`

**2. Magic numbers in survivability.lua**: Threat characteristics (lines ~100-140) use hardcoded range/speed/lethality values for SAM, fighter, and AAA threat types. These should be a configurable threat database, especially since new DCS units are added regularly.

**3. Voice recognition is stub code.** `voice_recognition.lua` (245 LOC) contributes to the project's LOC count and apparent feature set, but:
- `simulateAudioActivity()` always returns `false` (line 140)
- `transcribeAudio()` returns empty text with 0.0 confidence (lines 161-164)
- All three STT engine init functions are empty stubs returning `true`

For competition, this module should either be completed or clearly documented as a planned feature. Having stub code that appears functional but does nothing could be perceived negatively by reviewers.

**4. Inconsistent `require()` path prefix.** Some modules use `vigilai.src.` prefix (e.g., main.lua line 9: `require('vigilai.src.dcs.mission_integration')`), while command_processor.lua handlers use the same prefix. The test helper needs a custom searcher to remap these paths (test_helper.lua lines 21-42). This works but is fragile.

### Code Quality Score: 7/10

Solid foundations -- consistent naming, defensive checks, good comments in critical paths. Falls short on pcall protection, function decomposition, and the stub code issue.

---

## 5. Abstraction Layer Recommendations

### Recommendation 1: Extract Math Utilities (HIGH PRIORITY)

**Create**: `vigilai/src/core/math_utils.lua`

**Contents**:
```lua
local MathUtils = {}

function MathUtils.calculateRange(pos1, pos2)
    local dx = pos1.x - pos2.x
    local dy = pos1.y - pos2.y
    local dz = pos1.z - pos2.z
    return math.sqrt(dx*dx + dy*dy + dz*dz)
end

function MathUtils.calculateBearing(pos1, pos2)
    local dx = pos2.x - pos1.x
    local dz = pos2.z - pos1.z
    return math.atan2(dx, dz)
end

function MathUtils.calculateClosureRate(pos1, vel1, pos2, vel2)
    -- Consolidate from survivability.lua lines 504-536
end

function MathUtils.normalizeAngle(angle)
    -- Reusable angle normalization
end

return MathUtils
```

**Impact**: Eliminates 7 copy-pasted `calculateRange()` and 6 `calculateBearing()` implementations. Single point of maintenance. Could add unit tests for edge cases (zero distance, same position, etc.).

### Recommendation 2: DCS Time Abstraction (MEDIUM PRIORITY)

**Create**: `vigilai/src/core/time_provider.lua`

```lua
local TimeProvider = {}

function TimeProvider.getTime()
    if timer and timer.getTime then
        return timer.getTime()
    elseif DCS and DCS.getModelTime then
        return DCS.getModelTime()
    else
        return os.time()
    end
end

return TimeProvider
```

**Impact**: Fixes the `sensor_simulation.lua:40` DCS coupling leak. Provides consistent time source across all modules. Simplifies test mocking (only one function to stub).

### Recommendation 3: Event Bus for Subsystem Communication (LOW PRIORITY -- POST COMPETITION)

Currently, all subsystem communication flows through main.lua's update loop. An event bus would allow subsystems to react to specific events without polling:

```lua
local EventBus = {}
local listeners = {}

function EventBus.subscribe(event, callback)
    listeners[event] = listeners[event] or {}
    table.insert(listeners[event], callback)
end

function EventBus.publish(event, data)
    for _, callback in ipairs(listeners[event] or {}) do
        callback(data)
    end
end
```

**Use cases**:
- CombatManager publishes "threat_detected" -> PilotCoach subscribes for coaching triggers
- MissionManager publishes "objective_complete" -> DynamicObjectives subscribes for re-evaluation
- Survivability publishes "abort_recommended" -> MissionManager subscribes for mission state change

**Impact**: Reduces main.lua's orchestration burden. Enables subsystem autonomy. Not recommended before competition (adds complexity), but important for post-MVP architecture.

### Recommendation 4: Configuration Registry (MEDIUM PRIORITY)

Each module defines its own local `CONFIG` table. There are 10 separate CONFIG tables across the codebase. A centralized configuration registry would:

- Allow runtime configuration changes (e.g., from a settings UI)
- Provide a single place to document all tunable parameters
- Enable loading configuration from external files (useful for DCS mission editor integration)

```lua
local ConfigRegistry = {}
local configs = {}

function ConfigRegistry.register(module_name, defaults) ... end
function ConfigRegistry.get(module_name, key) ... end
function ConfigRegistry.set(module_name, key, value) ... end
function ConfigRegistry.loadFromFile(path) ... end

return ConfigRegistry
```

---

## 6. Competitive Differentiator Analysis

### Strong Differentiators (Competition Strengths)

**1. Physics-Based Sensor Simulation**

`advanced_sensor_simulation.lua` (702 LOC) implements a genuine radar range equation:

```lua
-- Line ~258
-- Pr = (Pt * G^2 * lambda^2 * sigma) / ((4*pi)^3 * R^4)
```

With:
- 7 sensor configurations across 3 modalities (APG-81/APG-77/APG-68 radars, EOTS/PIRATE IRST, 2 visual types)
- Environmental degradation factors (5 weather levels, 4 time-of-day periods, 4 terrain types)
- Sensor fusion with multi-sensor quality boost (1.2x quality, 1.3x confidence per additional sensor)
- Track history with variance-based stability calculation
- Jamming simulation support

**Why this differentiates**: Most DCS AI wingman mods use simple range checks. A physics-based sensor model with environmental factors demonstrates deep domain knowledge and creates emergent, realistic behavior (e.g., weather degrading radar performance forcing IRST reliance).

**2. Five-State Combat FSM**

`combat_manager.lua` implements a proper state machine with 5 states:

| State | Transitions To | Trigger |
|-------|---------------|---------|
| PASSIVE | DEFENSIVE, OFFENSIVE | Threat detected |
| DEFENSIVE | PASSIVE, EMERGENCY, OFFENSIVE | Threat assessment |
| OFFENSIVE | DEFENSIVE, EMERGENCY, PASSIVE | Engagement status |
| EMERGENCY | ABORT | Survival < threshold |
| ABORT | (terminal) | Mission abort |

With engagement queue (max 2 simultaneous), target prioritization (range + type + threat modifiers), and fuel-aware combat decisions (FUEL_RESERVE_COMBAT = 0.4).

**Why this differentiates**: Demonstrates a disciplined approach to AI behavior design. The state machine prevents illogical behavior transitions (e.g., going from ABORT back to OFFENSIVE) and creates predictable, debuggable AI.

**3. Dynamic Mission Adaptation**

`mission_manager.lua` (881 LOC, the largest module) and `dynamic_objectives.lua` (610 LOC) together provide:

- 5 mission types with distinct behavior profiles (CAP, ESCORT, STRIKE, SEAD, RECONNAISSANCE)
- 10-level task priority system (EMERGENCY_RTB=10 down to MAINTAIN_POSITION=1)
- Runtime objective generation based on 6 templates (threat response, opportunity target, fuel management, formation recovery, asset protection, intelligence gathering)
- Priority modifiers responsive to threat proximity, mission phase, fuel state, weapon inventory
- Adaptation history recording (documenting what changed and why)

**Why this differentiates**: The wingman doesn't just follow orders -- it adapts its behavior based on changing battlefield conditions. This is the kind of emergent intelligence that impresses competition judges.

**4. Pilot Training System**

`pilot_coach.lua` (631 LOC) and `training_scenarios.lua` (652 LOC) together create a dual-purpose product:

- 5 coaching categories with real-time triggers (formation drift, undetected threats, weapon range, energy state, communication delays)
- 8 progressive training scenarios (basic formation through multi-threat environment)
- Performance scoring with letter grades (A-F)
- Post-mission debrief generation with trend analysis (improving/declining/stable)
- Recommendation engine for identified weaknesses

**Why this differentiates**: Transforms the product from "AI wingman" to "AI wingman + flight instructor." This broadens the market (casual players want coaching; experienced players want the wingman) and adds a unique narrative for competition presentation.

### Moderate Differentiators

**5. Comprehensive Voice Command Architecture** -- The 35+ command vocabulary with 7 categories (combat, formation, navigation, status, mission, training, admin) in `command_processor.lua` shows thoughtful UX design. However, since the STT backend is stub code, this is currently a design differentiator, not a working feature.

**6. Weapon Engagement Model** -- `weapon_system.lua` models 4 weapon types (AIM-120C, AIM-9X, AGM-88, AGM-65) with full engagement envelopes (min/max range, altitude, aspect angle) and Pk calculations. The intercept point prediction for moving targets is a nice touch.

### Weak/Missing Differentiators

**7. No Multiplayer Support.** All references assume single-player (one player unit, one wingman unit). Modern DCS competitions increasingly emphasize multiplayer capability.

**8. No Learning/Adaptation.** The AI behavior is deterministic based on rules. There is no mechanism for the wingman to learn from past engagements or adapt to a specific player's style over time. Even a simple parameter adjustment system ("player prefers aggressive formations" -> adjust default formation spacing) would add a differentiator.

**9. No Mission Editor Integration.** The configuration is hardcoded in CONFIG tables. A DCS Mission Editor trigger-based configuration system would make the mod accessible to mission designers, dramatically increasing adoption potential.

### Competition Readiness Score: 7.5/10

The sensor simulation, combat FSM, and dynamic mission system form a strong technical story. The training system adds market breadth. The voice recognition stubs and lack of multiplayer are the main gaps.

---

## 7. LOC and Complexity Metrics

### Lines of Code Summary

| Category | Files | LOC | % of Total |
|----------|-------|-----|-----------|
| Source (Lua) | 16 | 8,248 | 78.1% |
| Tests (Lua) | 6 | 2,321 | 21.9% |
| **Total Code** | **22** | **10,569** | **100%** |
| Documentation (MD) | 3 | 2,203 | -- |
| CI Config (YAML) | 1 | 127 | -- |
| Blueprint (MD) | 1 | 151 | -- |

### Per-Module Breakdown

| Module | LOC | Functions | LOC/Function | Complexity |
|--------|-----|-----------|-------------|------------|
| mission_manager.lua | 881 | 34 | 25.9 | HIGH |
| advanced_sensor_simulation.lua | 702 | 26 | 27.0 | HIGH |
| license_manager.lua | 677 | 26 | 26.0 | MEDIUM |
| training_scenarios.lua | 652 | 24 | 27.2 | MEDIUM |
| main.lua | 640 | * | * | HIGH |
| pilot_coach.lua | 631 | 28 | 22.5 | MEDIUM |
| dynamic_objectives.lua | 610 | 21 | 29.0 | MEDIUM |
| survivability.lua | 549 | 22 | 24.9 | HIGH |
| combat_manager.lua | 518 | 28 | 18.5 | HIGH |
| command_processor.lua | 467 | 13 | 35.9 | MEDIUM |
| weapon_system.lua | 449 | 17 | 26.4 | MEDIUM |
| tactical_decision_engine.lua | 442 | 19 | 23.3 | HIGH |
| formation_controller.lua | 305 | 13 | 23.5 | LOW |
| mission_integration.lua | 298 | 13 | 22.9 | LOW |
| voice_recognition.lua | 245 | 16 | 15.3 | LOW |
| sensor_simulation.lua | 182 | 7 | 26.0 | LOW |

*main.lua function count omitted -- contains mixed initialization, utility, and update logic not comparable to domain modules.

### Complexity Hotspots

**1. mission_manager.lua** -- 881 LOC is the largest file. The `update()` function (starting around line 200) handles mission state checks, task priority evaluation, objective progress tracking, and adaptation logic in a single flow. The 34 functions suggest good decomposition, but the sheer size warrants splitting into `mission_state.lua` (state machine) and `mission_tasks.lua` (task management).

**2. `VigilAI.update()` in main.lua** -- 220 lines of sequential subsystem calls. This is the primary performance bottleneck since every subsystem runs every tick regardless of whether it has work to do.

**3. `WeaponSystem.evaluateTarget()`** -- Contains the Pk calculation pipeline: range validation, aspect angle computation, intercept point prediction, weapon selection from database, and launch zone validation. Each step has conditional logic based on weapon type. Complex but well-structured.

**4. `Survivability.update()`** -- Processes all threats, calculates closure rates, selects evasive maneuvers, and updates survival probability. The threat processing loop has O(n) complexity per threat with nested conditionals for threat type and range bands.

### Test-to-Code Ratio

```
Source LOC:  8,248
Test LOC:    2,321
Ratio:       0.28:1 (28 lines of test per 100 lines of source)
```

Industry benchmark for well-tested projects is typically 0.5:1 to 1:1. The ratio indicates moderate test coverage -- functional but not thorough. See Section 8 for detailed analysis.

---

## 8. Test Coverage Assessment

### Test Infrastructure

**Framework**: Custom test framework built in `test_helper.lua` and `run_tests.lua`. No external dependencies (no luaunit, busted, or luatest). This is pragmatic for DCS compatibility but limits test reporting capabilities.

**DCS Mock Environment** (`test_helper.lua`, 323 LOC):

Mocked globals:
- `timer` (getTime, scheduleFunction)
- `env` (info, warning, error)
- `trigger` (action.outText/outTextForCoalition/outTextForGroup/outTextForUnit/setUserFlag/smoke/explosion/signalFlare)
- `missionCommands` (addCommand, addSubMenu, removeItem, addCommandForCoalition, addSubMenuForCoalition)
- `coalition` (side.BLUE/RED/NEUTRAL, getGroups, getPlayers, getCountryCoalition)
- `world` (getAirbases, searchObjects, addEventHandler, removeEventHandler)
- `lfs` (writedir, currentdir, dir, mkdir, attributes)
- `Unit` (getByName -> MockUnit with full method set)
- `Group` (getByName -> mock group with controller)
- `country` (id.USA, id.RUSSIA)

MockUnit class (lines 89-130) implements all DCS unit methods including `getPoint()`, `getPosition()` (with full position matrix), `getVelocity()`, `getFuel()`, `getAmmo()`, `getLife()`, etc.

**Assessment**: The mock environment is comprehensive. It covers all DCS APIs used by the source modules. This is a strong foundation for testing.

### Test Suite Coverage

| Suite | File | Tests | Modules Tested |
|-------|------|-------|---------------|
| Combat | combat_system_test.lua | ~20 | weapon_system, survivability, combat_manager |
| Sensor/Training | sensor_training_test.lua | ~25 | advanced_sensor_simulation, pilot_coach, training_scenarios |
| Mission | mission_management_test.lua | ~25 | mission_manager, dynamic_objectives |
| Security | security_test.lua | ~19 | license_manager |

**Total estimated tests**: ~89 (BLUEPRINT.md claims 108; discrepancy may be from counting sub-assertions)

### Modules WITH Direct Tests

| Module | Test Coverage | Quality |
|--------|-------------|---------|
| weapon_system.lua | Init, status update, target evaluation, weapons free/hold | Good |
| survivability.lua | Init, survival probability range, threat level, abort conditions | Good |
| combat_manager.lua | Init, update, status, weapons authorization | Good |
| advanced_sensor_simulation.lua | Init, detection, multi-sensor fusion, environmental effects | Good |
| pilot_coach.lua | Init, coaching triggers, performance tracking | Good |
| training_scenarios.lua | Init, scenario management, completion tracking | Good |
| mission_manager.lua | Init, mission creation, task management, adaptation | Good |
| dynamic_objectives.lua | Init, objective generation, priority management | Good |
| license_manager.lua | Format validation, fingerprint, serialization, anti-tamper, hash, demo bypass | Excellent |

### Modules WITHOUT Direct Tests (GAPS)

| Module | LOC | Risk | Priority |
|--------|-----|------|----------|
| **tactical_decision_engine.lua** | 442 | HIGH | CRITICAL |
| **command_processor.lua** | 467 | HIGH | HIGH |
| **formation_controller.lua** | 305 | MEDIUM | MEDIUM |
| **main.lua** | 640 | MEDIUM | MEDIUM |
| **mission_integration.lua** | 298 | LOW | LOW (needs real DCS) |
| **voice_recognition.lua** | 245 | LOW | LOW (stub code) |
| **sensor_simulation.lua** | 182 | LOW | LOW (superseded by advanced) |

**Critical gap: TDE has zero tests.** The Tactical Decision Engine is the core AI brain of the project. Functions like `analyzeThreat()`, `evaluateSurvivalProbability()`, `selectOptimalWeapon()`, and `generateTacticalRecommendation()` determine all wingman behavior. Zero test coverage on the most important module is a significant competition risk.

**High-priority gap: command_processor.lua has zero tests.** This is the user-facing interface -- 35+ commands with pattern matching. Any regression in command parsing directly impacts user experience. Pattern matching bugs are common and easily caught by tests.

**Medium gap: formation_controller.lua has zero tests.** This is where the `setFormation()` mutation bug (Section 3) would have been caught by a simple test:
```lua
-- Hypothetical test
FormationController.setFormation("line_abreast", 1000)
FormationController.setFormation("line_abreast", 500)
-- Verify offset is 500, not 250 (which happens due to mutation bug)
```

### Performance Tests

The test suite includes performance benchmarks, which is excellent:

| Test | Workload | Threshold | Location |
|------|----------|-----------|----------|
| Combat update | 50 contacts, 10 iterations | < 0.1s avg | combat_system_test.lua:338-346 |
| Mission update | 15 contacts, 10 iterations | < 0.02s avg | mission_management_test.lua:~550 |
| Sensor detection | 20 targets, 10 iterations | < 0.05s avg | sensor_training_test.lua:~480 |
| Coaching update | 100 iterations | < 0.01s avg | sensor_training_test.lua:~500 |

These provide regression protection against performance degradation. Good practice.

### CI Pipeline

`.github/workflows/ci.yml` (127 LOC) runs 3 jobs:

1. **test**: Runs `lua5.3 tests/run_tests.lua` -- exits with code 1 on failure (CI-blocking)
2. **lint**: Runs `luacheck src/ --ignore 111 112 113 || true` -- **non-blocking** (`|| true`)
3. **security**: 5 checks (RCE patterns, encryption.lua removal, hardcoded secrets, demo bypass, license enforcement) -- CI-blocking on critical findings

**Issue**: The lint job uses `|| true`, meaning luacheck warnings never fail the build. This should be changed to fail on errors while allowing specific warned patterns. As configured, luacheck is decorative.

### Test Coverage Verdict: 6/10

Tested modules are well-covered with good assertion quality and performance benchmarks. But the complete absence of tests for TDE (the core AI engine), command_processor (the user interface), and formation_controller (with a known bug) is a material gap. The custom test framework works but lacks features like setup/teardown hooks, test isolation, and structured reporting.

**Competition preparation priority**:
1. Add TDE tests (threat analysis, weapon selection, survival probability)
2. Add command_processor tests (pattern matching for all 35+ commands)
3. Add formation_controller tests (will catch the mutation bug)
4. Make luacheck CI-blocking (remove `|| true`)

---

## Summary Scorecard

| Area | Score | Notes |
|------|-------|-------|
| Architecture | 7/10 | Clean hub-and-spoke; needs update loop decomposition |
| DCS Coupling | 8/10 | Excellent abstraction layer; 3 minor leaks |
| Modularity | 6.5/10 | Good domain boundaries; utility duplication is significant |
| Code Quality | 7/10 | Consistent style; needs pcall protection and stub cleanup |
| Competitive Differentiators | 7.5/10 | Strong sensor + combat + mission story; voice stubs are a gap |
| LOC/Complexity | -- | 8,248 source LOC across 16 files; well-distributed |
| Test Coverage | 6/10 | Core AI engine (TDE) completely untested |
| **Overall** | **7/10** | **Solid MVP. Address TDE tests, utility extraction, and formation bug before competition.** |

---

## Priority Action Items for Competition Preparation

### Must-Do (Before Competition)

1. **Add TDE test suite** -- Cover `analyzeThreat()`, `selectOptimalWeapon()`, `evaluateSurvivalProbability()`, `generateTacticalRecommendation()`. Estimated effort: 2-3 hours.

2. **Fix FormationController.setFormation() mutation bug** -- Deep-copy formation offsets before scaling. Estimated effort: 15 minutes.

3. **Extract math_utils.lua** -- Consolidate `calculateRange()` and `calculateBearing()` from 7+ modules. Estimated effort: 1 hour.

4. **Build missionContext once per tick** -- Eliminate 5x reconstruction in main.lua update loop. Estimated effort: 15 minutes.

5. **Add command_processor tests** -- Validate pattern matching for all command categories. Estimated effort: 2 hours.

### Should-Do (If Time Permits)

6. **Wrap VigilAI.update() in pcall** -- Prevent single errors from killing the mod. Estimated effort: 15 minutes.

7. **Decompose VigilAI.update()** into domain-specific update functions. Estimated effort: 1 hour.

8. **Make luacheck CI-blocking** -- Remove `|| true` from CI lint job. Estimated effort: 5 minutes + fixing any reported issues.

9. **Document or remove voice_recognition.lua stubs** -- Either complete the integration or add clear "PLANNED FEATURE" documentation. Estimated effort: 30 minutes.

### Nice-to-Have (Post Competition)

10. Event bus for inter-module communication
11. Configuration registry for centralized parameter management
12. Multiplayer support architecture
13. Player behavior learning/adaptation system
