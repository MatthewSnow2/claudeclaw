# ST Metro Pipeline

Last updated: 2026-02-25 23:45 CST

This file tracks all in-progress, planned, and parked work across the ST Metro ecosystem. Referenced in daily reports.

---

## PRIORITY 1 - This Week (Before Sunday 2026-03-01)

### ST Metro Deployment
Get the ecosystem actually running. Currently only EA-Claude/Data is live.

- [x] Deploy Metroplex as systemd service - RUNNING (enabled, PID active)
- [x] Configure research agents cron schedule (user crontab: daily 5am + weekly)
- [x] Schedule Sky-Lynx weekly run (user crontab: Sunday 2am)
- [x] Smoke test: Metroplex active, research agents dry-run OK, queue has 2 items
- [x] Verify ST Factory DB connectivity from Metroplex -- VERIFIED 2026-02-25 (2 patches, 8 recs, 2 outcomes read OK)

---

## PRIORITY 2 - Next Up

### EA-Claude Async Dispatch
Replace blocking single-session model with async worker dispatch.

- [ ] Add task duration estimation to Data
- [ ] Implement async dispatch in bot.ts / agent.ts
- [ ] Starscream worker process (pm2) - social media, Late API
- [ ] Ravage worker process (pm2) - coding + GitHub review
- [ ] Soundwave worker process (pm2) - research + HIL coaching
- [ ] All agents integrated into Sky-Lynx improvement loop
- [ ] Soundwave reads from Metroplex/ST Factory to surface HIL bottlenecks
- Note: Single Telegram bot (Data), no separate bot IDs needed

### Data Challenger Mode (Christensen Filter) -- DONE
Stop building for building's sake. Focus on M2AI brand and revenue.

- [x] Update CLAUDE.md with Christensen filter prompt (lines 35-59)
- [x] Data defaults to "what job does this perform?" before executor mode on new ideas
- [x] Define trigger conditions (new project idea vs. execution request)

---

## PRIORITY 3 - Pipeline (Planned, Not Urgent)

### Gemini 3.1 Pro Integration for Data
Multi-LLM for logic/reasoning tasks. Two opposing minds.

- Model: Gemini 3.1 Pro (in preview, available via Gemini API)
- Key benchmark: ARC-AGI-2 77.1% (logic/abstract reasoning)
- Pricing: $2/$12 per 1M tokens - comparable to Claude
- Use case: Data routes logic-heavy analysis to Gemini, synthesizes both perspectives
- Already have GOOGLE_API_KEY in ~/.env.shared
- [ ] Design routing logic (when does Data call Gemini vs. handle inline?)
- [ ] Implement Gemini API call in agent.ts or as separate util
- [ ] Test on reasoning-heavy queries

### Daily Reports (Scheduled) -- DONE
Morning briefing + evening review via Telegram + dashboard.

- [x] Morning report scheduled (8am)
- [x] Evening review scheduled (4pm / 1600)
- [x] Data Dashboard v1 built (localhost:8080/claudeclaw/dashboard/)
- [x] Report generator script (dashboard/generate_report.py) reads live system state
- [x] Scheduled tasks generate dashboard JSON before sending Telegram summaries
- Format: What's done, what's left, pipeline items needing attention

---

## PRIORITY 3 (continued) - Other Pipeline Items

### Agentic SCM Proposal (ACTIVE - Group wants discussion)
Origin: Matthew pitched agentic SCM in group chat (2026-02-23). Group interested, wants proposal.
Core thesis: Replace traditional ETL forecasting with agent-driven real-time SCM.
- [ ] Draft slide deck (for Skool AI community / incubator group -- practice run, low stakes)
- [ ] Define market segments: mid-tier enterprise, SMB, owner/operator services
- [ ] Value prop doc: faster distro, real-time replenishment, automated purchase cycles
- [ ] DSP as live demo (see below)
- Note: This aligns with beachhead market candidate "SCM + AI" from monetization strategy

### DSP Game -> Agentic SCM POC (mcp-dsp-game)
Evolution: DSP is literally an ETL + SCM simulator. Use it as POC for the real-world SCM pitch.
Current state: Phases 0-3 mostly done (save parser, BepInEx plugin, real-time integration, optimization engine). Phase 4 CI/CD in progress.
- [ ] Review current mcp-dsp-game state (last touched Dec 2024)
- [ ] Extend: autonomous agent that adjusts production chains, not just reports
- [ ] Add demand forecasting based on consumption rates
- [ ] Add automated rebalancing (agent equivalent of Walmart's SCM)
- [ ] Create demo workflow: agent manages DSP supply chain in real-time
- Note: Doubles as portfolio piece + SCM proposal demo

### AI Video Generation (Private, Personal)
Approach: Seedance 2.0 (ByteDance cloud) or local via ComfyUI + Wan 2.1/HunyuanVideo.
Inspiration: Tianyu Xu's classes/videos, Superman vs Dr. Strange Seedance viral demo.
- [ ] Start simple: pull reference images, generate test clips from stills
- [ ] Lower Decks continuation: animate existing comic panels (simpler -- source images exist, consistent style)
- [ ] Robotech New Generation scene: storyboard Cyclones vs Invid + Alpha rescue (~15-20 shots)
- [ ] Pull Robotech reference images from online for characters/mechs
- Note: Lower Decks first (POC), Robotech second (complex). Gaming PC (RTX 5080).

### ST Metro Visual Story/Guide
- [ ] Narrative structure: tell the ecosystem story for non-engineers
- [ ] Slide deck / visual presentation (for Skool community + personal reference)
- [ ] Cover: idea capture (CD + research agents), IdeaForge, Ultra-Magnus pipeline, yce-harness, ST Factory, Sky-Lynx loop, Metroplex L5 layer
- Note: Not a technical spec. A visual narrative showing the flow. Audience: Skool incubator group.

### VisionClaw (Meta Ray-Ban Smart Glasses) -- UNPARKED
DAT SDK now available via GitHub Packages. Blocker cleared.
- Reference: https://github.com/sseanliu/VisionClaw
- Android: API 34+, Android Studio, GitHub PAT with read:packages for DAT SDK auth
- iOS: iOS 17+, Xcode 15+
- Both need: Gemini API key (already have GOOGLE_API_KEY)
- [ ] Clone repo and review current codebase
- [ ] Set up DAT SDK access (GitHub PAT with read:packages)
- [ ] Determine target platform (Android or iOS -- Matthew's phone?)
- [ ] Build and test sample app
- [ ] Integrate with OpenClaw/ClawdBot for agentic capabilities

---

## PARKED - Low Priority

### ComfyUI Video Generation (Gaming PC)
- Status: Fully set up, models downloaded, custom nodes installed
- Models: SVD xt (8.9GB), AnimateDiff v3 (1.56GB), SD 1.5 (3.97GB)
- Custom nodes: AnimateDiff-Evolved, VideoHelperSuite
- Launch: start_comfyui.bat (manual, cannot run headless)
- Note: Robotech scene moved to Priority 3 as dedicated item

### Beth2.0 (Stacey's Agent)
- On hold per Matthew's request. Stacey not ready.
- **Stacey's current setup**: ChatGPT on phone, conversational, voice-first interaction
- **Use cases**: General info, medical questions/summarizations, no custom GPTs or special tools
- **Key requirement**: Voice integration (she uses voice to interact conversationally)
- **Comms options**: WhatsApp (Twilio, recommended), Telegram, Discord, Web chat, SMS
- **Tech needs**: STT (Whisper/Deepgram) + TTS (ElevenLabs/OpenAI) + mobile-friendly interface
- Would need: bot token for chosen platform, independent persona/CLAUDE.md, pm2 process
- Resume when: Stacey is ready

### NAS Integration (Asustor AS5402T)
- On hold: power outage bricked the unit, warranty claim in progress
- Resume when: NAS is back online

### SCM Simulation Game (standalone concept)
- Marked as "if" -- future possibility, not active
- If revisited: could be a purpose-built SCM game (not DSP mod) for training/demo
- Note: DSP-as-POC and Agentic SCM Proposal cover the real use case

### Starscream - Full Automation
- Current state: LinkedIn connected, HIL review gate in place, voice guide done
- Parked: Full automation until async dispatch is built (Priority 2)

---

## CLOSED

- [x] EA-Claude (Data) deployed via pm2, running as Telegram bot (@m2ai_data_bot)
- [x] ClaudeClaw upstream V1 cherry-picks applied (voice, video, retry logic, etc.)
- [x] Late API integrated (social-media skill, LATE_API_KEY in ~/.env.shared)
- [x] LinkedIn account connected (Matthew Snow, expires 2026-03-23)
- [x] Matthew's voice guide saved to social-media skill
- [x] LinkedIn repost of Mark Kashef ClaudeClaw post (done manually)
- [x] ComfyUI installed on gaming PC (RTX 5080, Python 3.11, CUDA 12.8)
- [x] Video gen models downloaded to gaming PC
- [x] Metroplex Phase 9 built and committed (not deployed)
- [x] ST Metro Roadmap Phases 1-7f completed (per prior sessions)
- [x] Research agents rewired to write to IdeaForge
- [x] **ST Metro deployed** - Metroplex (systemd, active), research agents (cron, ran 5am today), Sky-Lynx (cron, Sundays 2am)
- [x] ST Factory DB connectivity verified from Metroplex (2 patches, 8 recs, 2 outcomes)
- [x] Unified Funnel all 4 phases complete (idea-surfacer -> IdeaForge -> Metroplex triage)
- [x] Metroplex triage dedup bug fixed (was spamming "Triage approved 2" every minute)
- [x] **Wheelie Nano setup** - SSH from ProBook, passwordless sudo, disk cleanup (93%->80%), ROS2 Humble verified, f1tenth_ws rebuilt clean (18 packages, vesc/ackermann/f1tenth_stack all functional)
- [x] Blurr full architecture context saved to Perceptor
- [x] Data Challenger Mode (Christensen filter) implemented in CLAUDE.md
