# ST Metro Pipeline

Last updated: 2026-02-27 CST

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
- [x] Starscream M-F 1000 posting (scheduled task, Late API, HF image gen, Imgur hosting, HIL review)
- [ ] Starscream full worker process (pm2) - async dispatch integration
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
Approach: Local via ComfyUI + Wan 2.2/HunyuanVideo/LTX-2. Seedream 5.0 Lite is cloud-only (skip for video).
Inspiration: Tianyu Xu's classes/videos, Superman vs Dr. Strange Seedance viral demo.
Setup guide: `claudeclaw/docs/COMFYUI_VIDEO_SETUP.md` (updated 2026-02-27)
Workflow JSON: `claudeclaw/docs/workflows/wan22_i2v_14b_fp8_480p.json` (importable)
Validation script: `claudeclaw/scripts/validate_comfyui_env.py`
- [x] Setup docs completed with verified download URLs, dual-expert workflow, VRAM budget
- [x] Importable ComfyUI workflow JSON created (14 nodes, dual KSampler MoE architecture)
- [x] Environment validation script created (checks GPU, CUDA, RAM, disk, models)
- [ ] Download Wan 2.2 I2V 14B FP8 models to gaming PC (~37GB -- TWO diffusion models + text encoder + VAE + CLIP vision)
- [ ] Download HunyuanVideo 1.5 I2V FP8 models (~19GB -- cfg-distilled variant)
- [ ] Run validate_comfyui_env.py on gaming PC to confirm readiness
- [ ] Import workflow JSON and test Wan 2.2 I2V at 480p with sample image
- [ ] Start simple: pull reference images, generate test clips from stills
- [ ] Lower Decks continuation: animate existing comic panels (simpler -- source images exist, consistent style)
- [ ] Robotech New Generation scene: storyboard Cyclones vs Invid + Alpha rescue (~15-20 shots)
- [ ] Pull Robotech reference images from online for characters/mechs
- Note: Lower Decks first (POC), Robotech second (complex). Gaming PC (RTX 5080, 16GB VRAM).
- Note: Wan 2.2 uses dual-expert MoE (high-noise + low-noise models). Requires 32GB+ system RAM for offloading.
- Note: SVD xt/AnimateDiff now legacy. Seedream 5.0 Lite is cloud-only, skip for video gen.

### VisionClaw (Meta Ray-Ban Smart Glasses) -- ACTIVE
DAT SDK now available via GitHub Packages. Target: Android.
- Reference: https://github.com/sseanliu/VisionClaw
- Cloned to: `/home/apexaipc/projects/visionclaw/`
- Android project: `samples/CameraAccessAndroid/`
- APK: `app/build/outputs/apk/debug/app-debug.apk` (146MB)
- Auth: `~/.env.shared` GITHUB_TOKEN has write:packages (implies read:packages)
- Secrets.kt: Gemini API key configured from env.shared
- ProBook: Android CLI tools + SDK installed at `~/android-sdk/`, Java 17, Gradle 8.14.1
- AlienPC: Android Studio installer downloaded to `C:\Users\matth\Downloads\android-studio-installer.exe`
- [x] Clone repo and review current codebase
- [x] Set up DAT SDK access (GitHub PAT with read:packages via env.shared)
- [x] Determine target platform -- Android
- [x] Build debug APK on ProBook (CLI)
- [ ] Install Android Studio on AlienPC (installer ready)
- [ ] Sideload APK to Android phone via ADB
- [ ] Test glasses connection + camera stream
- [ ] Integrate with OpenClaw/ClawdBot for agentic capabilities

---

## PARKED - Low Priority

### ComfyUI Video Generation (Gaming PC)
- Status: Setup docs complete, importable workflow ready, validation script ready. Awaiting model downloads on gaming PC.
- Legacy models (still installed): SVD xt (8.9GB), AnimateDiff v3 (1.56GB), SD 1.5 (3.97GB)
- Upgrade path: Wan 2.2 I2V 14B FP8 (~37GB), HunyuanVideo 1.5 I2V FP8 (~19GB), LTX-2 (optional)
- Docs: `docs/COMFYUI_VIDEO_SETUP.md`, `docs/workflows/wan22_i2v_14b_fp8_480p.json`, `scripts/validate_comfyui_env.py`
- Custom nodes needed: VideoHelperSuite (installed), ComfyUI-GGUF (optional for quantized models)
- Launch: start_comfyui.bat (manual, cannot run headless)
- Note: Merged into Priority 3 "AI Video Generation" item. This parked entry is reference only.

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
- [x] Async dispatch Phase 1 implemented (dispatch_queue, classifier, result-poller, bot.ts)
- [x] Soundwave dashboard section live (reads ST Factory recs, patches, queue, signals)
- [x] VigilAI competition report generated (AI Fight Club, AI Grand Prix, BVR Gym)
- [x] **Registered for Anduril AI Grand Prix** (theaigrandprix.com, virtual qualifiers Apr-Jun 2026)
- [x] **ST Metro Visual Story/Guide** -- narrative structure, slide deck, ecosystem visual (st-metro-visual-story.html, 97KB)
- [x] Classifier discussion guard fix (isQuestion/isMetaDiscussion checks prevent false dispatch on worker-name mentions)
- [x] Healthcare LinkedIn scheduled task (Starscream, M-F 1100, separated from general post by 1hr)
