# Robotech New Generation - AI Video Episode Production Plan

**Created:** 2026-02-28
**Updated:** 2026-03-01 (v4: Wan2GP optimizer, VACE 1.3B lightweight, Video2X upscale pipeline, retro anime LoRA, Wan 2.6 cloud/local clarification, refined gen times)
**Scene:** Cyclones vs Invid + Alpha Rescue
**Target:** ~15-20 shots, 60-90 seconds total runtime
**Hardware:** Gaming PC - RTX 5080 16GB (GDDR7, 960 GB/s bandwidth, 1801 AI TOPS), 32GB RAM, Windows

---

## 0. Strategic Recommendation: Lower Decks POC First

**Verdict: Do Lower Decks first. Robotech second.**

| Factor | Lower Decks | Robotech New Gen |
|--------|-------------|------------------|
| Source images | Exist (comic panels, screencaps) | Must be created/sourced |
| Art style | Flat, clean, consistent colors | Detailed mecha, variable lighting |
| Motion complexity | Simple (talking heads, walking) | Complex (transformations, flight, combat) |
| Reference consistency | High (established character sheets) | Low (multiple mecha modes, Invid variants) |
| Iteration cost | Low (3-5 min per 480p clip) | High (10-15 min per clip, more regens) |
| I2V suitability | Excellent (clear subjects, simple BGs) | Challenging (mechanical movement, explosions) |
| POC value | Proves pipeline works end-to-end | Requires proven pipeline to succeed |

**Lower Decks POC scope:** 3-5 shots, single scene, one character doing simple actions (talking, head turn, walking). This validates the entire ComfyUI workflow, prompt engineering patterns, and output quality before investing in the complex Robotech scene.

**Graduate to Robotech when:**
- [x] Wan 2.2 I2V workflow produces clean 5-second clips at 480p
- [x] You've dialed in prompt patterns that control motion without distorting style
- [x] You understand how CLIP Vision conditioning affects output consistency
- [x] You've tested at least 10 generations to understand failure modes

---

## 1. Model Selection & Capabilities

### Primary: Wan 2.2 I2V 14B (FP8)
- **Role:** Hero shots, all character close-ups, Alpha Fighter scenes
- **Why:** Best open-source I2V quality. Dual-expert MoE (27B total params, 14B active per step) preserves source image fidelity while adding motion. Trained on +65.6% more images and +83.2% more videos vs Wan 2.1. CLIP Vision conditioning keeps character/mech design consistent frame-to-frame.
- **Resolution:** 832x480 (16:9-ish) or 480x832 (portrait for close-ups)
- **Duration:** 81 frames = ~5 seconds at 16fps
- **RTX 5080 time:** ~7-10 min per clip FP8 (with SageAttention: ~4-5 min; with Wan2GP + NV FP4: ~3-4 min)
- **GGUF option:** Q4_K quantization drops VRAM to ~6-8GB, enables 720p. Slightly lower quality but viable for B-roll shots.
- **Wan2GP optimizer:** [deepbeepmeep/Wan2GP](https://github.com/deepbeepmeep/Wan2GP) enables Wan 2.2 on 6-12GB VRAM cards. NV FP4 checkpoints give 30%+ faster generation on RTX 50-series with PyTorch 2.9.1 / CUDA 13. Consider this if SageAttention alone isn't fast enough.
- **Setup:** Native ComfyUI nodes. Workflow JSON ready at `docs/workflows/wan22_i2v_14b_fp8_480p.json`
- **GGUF models:** Available at [bullerwins/Wan2.2-I2V-A14B-GGUF](https://huggingface.co/bullerwins/Wan2.2-I2V-A14B-GGUF) -- Q3_K_M through Q8 quantization levels
- **Animate variant:** [Wan-AI/Wan2.2-Animate-14B](https://huggingface.co/Wan-AI/Wan2.2-Animate-14B) -- dedicated animation model, may produce cleaner results for cel-shaded anime content. Worth A/B testing against standard I2V model.

### Secondary: HunyuanVideo 1.5 I2V (FP8 cfg-distilled)
- **Role:** Backup/comparison, potentially better for stylized content
- **Why:** Lighter VRAM footprint (~8-10GB), faster generation with cfg-distilled (12-step mode), good for quick iteration
- **Resolution:** 832x480
- **Duration:** 49 frames = ~3 seconds
- **RTX 5080 time:** ~4-6 min per clip (cfg-distilled, 12 steps)
- **Use case:** Quick previews, A/B comparison with Wan 2.2, potentially better for Invid organic designs

### Tertiary: LTX-2 (NVFP4) -- Major Upgrade Jan 2026
- **Role:** Rapid previsualization AND potential hero shots for simpler scenes
- **Architecture:** 19B parameter DiT-based audio-video foundation model (full open-source release Jan 2026)
- **Why:** Native 4K resolution (3840x2160), synchronized audio+video in single pass, up to 50fps output. NVFP4 optimized for RTX 50-series. Runs on 12GB+ VRAM.
- **Resolution:** 540p for previs, up to 4K for final output
- **Duration:** Up to 20 seconds at 4K
- **RTX 5080 time:** ~1-2 min per clip (480p previs), longer at 4K
- **Audio bonus:** Generates matched audio alongside video -- could provide scratch SFX for Invid screeches, weapon fire, engine sounds
- **Anime capability:** Confirmed to produce flat cel-shaded textures and clean outlines matching classic 2D cartoon styles via prompt engineering
- **Limitation:** Newer model, less battle-tested for anime I2V than Wan 2.2. Best used for previs and audio scratch tracks, graduate to hero shots after testing.
- **Source:** [Lightricks/LTX-2 (HuggingFace)](https://huggingface.co/Lightricks/LTX-2)

### Upgrade Path: Wan 2.6 I2V (December 2025, current as of March 2026)
- **Role:** Drop-in replacement for Wan 2.2 once pipeline is proven. THE model for multi-shot Robotech production.
- **IMPORTANT: Wan 2.6 is a separate product line from Alibaba, not a direct version successor to Wan 2.2.** Different architecture and release track. Both coexist.
- **Key new capabilities:**
  - **R2V (Reference-to-Video):** Upload 2-30 second reference video. Model extracts appearance from up to **150 reference frames** and maintains identity for up to **3 simultaneous characters**. Preserves facial structure, clothing details, body proportions, and even voice characteristics. This solves the #1 risk in the shot list: inconsistent mecha/character design across shots.
  - **Multi-shot logic:** Prompt "CUT TO" transitions and the model generates editorially coherent shot changes within a single generation.
  - **15-second clips** (3x longer than Wan 2.2's 5s native)
  - **Native audio-visual sync** with lip-sync and ambient sound
- **Current access:** Primarily **cloud API** via fal.ai, WaveSpeed, Atlas Cloud. NOT yet available as a local model with native ComfyUI support like Wan 2.2. A "Wan 2.6 Flash" variant exists via WaveSpeedAI for faster cloud inference. Local ComfyUI integration is emerging but not mature as of March 2026.
- **Why wait:** Cloud API adds latency and cost vs local generation. Prove the pipeline on Wan 2.2 locally first, then evaluate whether R2V's consistency gains justify the cloud dependency. Check ComfyUI wrapper status monthly.
- **When to adopt:** After Phase 1 (Lower Decks POC) is complete. If R2V character consistency is significantly better than VACE + I2V chaining, it's worth the cloud cost for the Robotech multi-shot production. Budget ~$0.10-0.30 per generation via API.

### Not Used: Seedream 5.0 Lite
- **Role:** Reference image generation only (cloud API via ComfyUI Partner Nodes)
- **Why:** Image gen only, not video. Web-connected retrieval could help generate Robotech-accurate reference art if you describe the mecha/characters. Cloud-based, requires BytePlus account.
- **Skip for video pipeline.** Potentially useful for generating clean reference images if you can't find good source material online.

### Model Comparison Matrix (March 2026)

| Capability | Wan 2.2 14B | Wan 2.6 | HunyuanVideo 1.5 | LTX-2 |
|-----------|-------------|---------|-------------------|-------|
| Total params | 27B (14B active) | ~14B (est.) | 8.3B | 19B |
| Architecture | MoE (2 experts) | MoE (enhanced) | DiT | DiT |
| I2V quality | Best | Best+ | Very good | Good-great |
| Anime/cel-shaded | Excellent (LoRAs) | Excellent | Good (LoRAs avail) | Good (prompt-driven) |
| Audio generation | No | **Yes (sync)** | No | **Yes (synchronized)** |
| Max resolution | 720p | 1080p | 720p | **4K native** |
| Max clip length | 5s | **15s** | 3s | **20s** |
| R2V (char consistency) | No | **Yes (3 chars, 150 frames)** | No | No |
| Multi-shot in 1 gen | No | **Yes (CUT TO)** | No | No |
| VACE ControlNet | Yes (14B + 1.3B) | TBD | No | No |
| 16GB VRAM fit | Yes (FP8) | **Cloud API only** | Yes (FP8 distilled) | Yes (NVFP4) |
| Gen time (480p 5s, RTX 5080) | 3-10 min* | Cloud (~5s API) | 1-1.5 min | 10-15 sec |
| GGUF quantized | Available (Q3-Q8) | N/A (cloud) | Available | Available |
| ComfyUI native | Yes | **Cloud API** | Yes | Yes |
| Open source | Yes | Yes (weights) | Yes | Yes (full, Jan 2026) |
| Local inference | **Yes** | **No (cloud only)** | **Yes** | **Yes** |

*Wan 2.2 range: 3-4 min (Wan2GP+FP4) / 4-5 min (SageAttention) / 7-10 min (baseline FP8)

---

## 2. Scene Synopsis

**Setting:** Earth, Third Robotech War. A resistance group on Cyclone ride armor is ambushed by Invid Scouts and Troopers in a ruined urban environment. During the desperate fight, an Alpha Fighter arrives from orbit, transforms to Battloid mode, and turns the tide.

**Narrative beats:**
1. **Establish** - Cyclone riders moving through ruins (tension)
2. **Contact** - Invid swarm appears (alarm)
3. **Combat** - Cyclones vs Invid ground fight (action)
4. **Crisis** - Overwhelmed, riders fall back (desperation)
5. **Rescue** - Alpha Fighter streaks in, transforms, opens fire (relief/triumph)
6. **Resolution** - Invid scatter, riders regroup (denouement)

---

## 3. Shot List (18 Shots)

Each shot is one I2V generation: a single reference image animated for ~5 seconds.

### Act 1: Establish (Shots 1-4)

| # | Shot | Camera | Duration | Motion Description | Reference Image Needs |
|---|------|--------|----------|--------------------|-----------------------|
| 1 | **Wide establishing** - Ruined city street, dust, overcast sky | Wide, static, slightly low angle | 5s | Slow dust particle drift, subtle light flicker on ruins | Ruined urban landscape, post-apocalyptic, Robotech aesthetic |
| 2 | **Medium tracking** - Three Cyclone riders in motorcycle mode moving through debris | Medium, tracking left to right | 5s | Cyclones moving at speed, debris passing | 3 Cyclone motorcycles (VR-052, blue/red/green) on ruined road |
| 3 | **Close-up** - Lead rider (Scott Bernard) in CVR-3 helmet, visor reflecting ruins | Close-up, slight dutch angle | 5s | Subtle head movement, visor reflection shimmer, breathing | Scott Bernard in CVR-3 armor, blue accents, helmet visor |
| 4 | **POV/over-shoulder** - HUD overlay, road ahead through Scott's visor | First-person, slight camera shake | 5s | Road rushing toward camera, HUD elements subtle | Cyclone cockpit POV with HUD overlay on ruined road |

### Act 2: Contact (Shots 5-7)

| # | Shot | Camera | Duration | Motion Description | Reference Image Needs |
|---|------|--------|----------|--------------------|-----------------------|
| 5 | **Sky shot** - Dark shapes emerging from clouds, Invid Scouts descending | Low angle looking up, wide | 5s | Invid silhouettes swooping down through clouds, organic movement | Invid Scout silhouettes against cloudy sky, descending |
| 6 | **Reaction** - Scott's head snaps up, hand reaches for weapon | Medium close, eye level | 5s | Quick head turn upward, arm reaching to side | Scott in Cyclone armor, alert pose, reaching for weapon |
| 7 | **Wide reveal** - Swarm of 6-8 Invid Scouts and 2 Troopers, full reveal | Wide, slight high angle | 5s | Invid hovering/circling, organic pulsing glow from sensor eyes | Invid swarm formation - Scouts (crab-like) + Troopers (humanoid) |

### Act 3: Combat (Shots 8-13)

| # | Shot | Camera | Duration | Motion Description | Reference Image Needs |
|---|------|--------|----------|--------------------|-----------------------|
| 8 | **Transformation** - Cyclone unfolds from motorcycle to power armor | Medium, side angle | 5s | Mechanical unfolding animation, rider standing up in armor | Cyclone mid-transformation sequence (bike to armor) |
| 9 | **Action** - Cyclone rider fires EP-37 at incoming Scout | Medium, dynamic angle | 5s | Arm raised, muzzle flash, energy bolt streaking toward Invid | Cyclone in battle armor firing EP-37 pulse rifle |
| 10 | **Invid hit** - Scout takes hit, green fluid sprays, crashes | Close-medium, tracking | 5s | Invid recoiling from impact, sparks and fluid, falling | Invid Scout being hit, green protoculture fluid spraying |
| 11 | **Counter-attack** - Invid Trooper fires annihilation disc | Medium, low angle on Trooper | 5s | Energy charging in claw, disc projectile launching | Invid Trooper (humanoid) firing energy weapon from claw |
| 12 | **Dodge/impact** - Cyclone rider dives, explosion behind | Wide, dynamic | 5s | Rider diving/rolling, debris and fire erupting behind | Cyclone rider mid-dodge with explosion in background |
| 13 | **Overwhelmed** - Multiple Invid closing in, riders back-to-back | Wide overhead or medium | 5s | Invid circling closer, riders shifting defensive positions | Three Cyclone riders surrounded by Invid, defensive formation |

### Act 4: Rescue (Shots 14-17)

| # | Shot | Camera | Duration | Motion Description | Reference Image Needs |
|---|------|--------|----------|--------------------|-----------------------|
| 14 | **Sky streak** - Alpha Fighter in jet mode screaming overhead | Low angle, wide, fast pan | 5s | Fighter streaking across frame at high speed, contrail | VFA-6 Alpha Fighter in jet mode, blue color scheme, overhead |
| 15 | **Transformation** - Alpha converting jet to Guardian to Battloid | Medium-wide, tracking | 5s | Sequential mech transformation, wings folding, legs extending | Alpha Fighter mid-transformation sequence |
| 16 | **Battloid fires** - Alpha in Battloid mode, GU-XX gun pod blazing | Medium, slight low angle (heroic) | 5s | Gun pod firing rapid bursts, shell casings, muzzle flash | Alpha Battloid standing, gun pod raised, firing stance |
| 17 | **Invid scatter** - Remaining Invid retreating, two exploding | Wide, high angle | 5s | Invid turning and fleeing, explosions, green energy dissipating | Invid scattering/fleeing, explosions in background |

### Act 5: Resolution (Shot 18)

| # | Shot | Camera | Duration | Motion Description | Reference Image Needs |
|---|------|--------|----------|--------------------|-----------------------|
| 18 | **Regroup** - Alpha Battloid stands among ruins, Cyclone riders approach | Wide, golden hour lighting | 5s | Slight mech idle sway, riders walking toward it, dust settling | Alpha Battloid standing heroically, Cyclone riders approaching |

---

## 4. Reference Image Requirements

### Images to Source/Create (18 total)

**Priority 1 - Must have before any generation:**
- Cyclone VR-052 in motorcycle mode (blue, red, green variants)
- Cyclone in battle armor mode (full body, clear detail)
- Scott Bernard in CVR-3 armor (helmet on)
- VFA-6 Alpha Fighter - jet mode, battloid mode
- Invid Scout (crab-like design, sensor eye)
- Invid Trooper (humanoid, larger)

**Priority 2 - Scene-specific compositions:**
- Ruined urban environment (Robotech New Gen aesthetic)
- Cyclone transformation mid-sequence
- Alpha Fighter transformation mid-sequence
- Combat action poses (firing, dodging)

### Where to Source

| Source | What | Notes |
|--------|------|-------|
| [Robotech.com Mecha Database](https://robotech.com/roboverse/mecha-database/category/new-generation) | Official mecha reference art | Clean, canonical designs |
| [Robotech Wiki (Fandom)](https://robotech.fandom.com/wiki/Cyclone) | Screenshots, episode stills | Good for scene composition |
| Episode screencaps (Genesis Climber MOSPEADA / Robotech: New Gen) | Direct anime frames | Best for I2V - already animated style |
| Toynami/Pose+ figure photos | 3D reference for mecha | Good angles, clean backgrounds |
| AI image generation (Seedream 5.0 Lite or Flux) | Custom compositions | Generate specific poses/angles not available in existing art |

### Image Preparation Guidelines
- **Resolution:** At least 832x480 (or crop to match). Wan 2.2 uses the input image as frame 1.
- **Clean backgrounds preferred.** Busy backgrounds confuse the motion model.
- **Single clear subject per image.** For group shots, ensure subjects are well-separated.
- **Consistent style across shots.** If mixing screencaps with AI-generated refs, process them through the same style filter.
- **No text/UI overlays.** Remove watermarks, logos, subtitle text.

---

## 5. Technical Production Pipeline

### Per-Shot Workflow

```
1. Select/create reference image
   |
2. Prepare image (crop to 832x480, clean up, remove text)
   |
3. [Optional] Quick preview with LTX-2 (~1-2 min)
   |-- If composition/motion doesn't work, adjust ref image or prompt
   |
4. Generate with Wan 2.2 I2V at 480p production settings
   |-- Load workflow: wan22_i2v_14b_fp8_480p.json
   |-- Upload ref image to Load Image node
   |-- Set positive prompt (motion description from shot list)
   |-- Set negative prompt (standard: "blurry, distorted, low quality, static, morphing, deformed, flickering, jittery")
   |-- Queue Prompt
   |-- Wait ~10-12 min (or ~5-6 min with SageAttention)
   |
5. Review output
   |-- Accept: move to post-processing
   |-- Reject: adjust seed, prompt, or ref image, regenerate
   |-- Expect 2-3 generations per shot on average
   |
6. Post-processing
   |-- Upscale if needed (RTX Video Super Resolution or Topaz)
   |-- Color grade for scene consistency
   |-- Add to timeline in video editor
```

### Prompt Engineering Strategy

**Structure:** `[subject motion], [camera direction], [lighting/mood], [style anchor]`

Lead with motion, not appearance. The model already knows what things look like from the reference image. Describe how the subject *moves*, not what it *is*.

**Example (Shot 9):**
```
Positive: "Armored mecha soldier raises arm and fires pulse rifle,
energy bolt streaking from weapon barrel, muzzle flash illuminating armor,
camera holds medium angle with slight push-in,
dramatic rim lighting, overcast sky,
An1meStyl3 cel-shaded, metallic surface detail, smooth animation"

Negative: "blurry, distorted, low quality, static, morphing, deformed,
flickering, jittery, melting, face distortion, extra limbs,
((realistic)), ((photograph)), live action"
```

**Key rules for mecha I2V prompts:**
- Focus on **motion**, not appearance (appearance comes from the ref image)
- Be specific about **what moves** ("arm raises and fires" not "combat action")
- Use camera movement as a secondary layer, not primary driver
- Keep facial/cockpit regions stable with micro-movements (large rotations cause identity drift)
- Anchor lighting/focal length to what's already visible in the source image
- Keep CFG at 3.0-3.5 (Wan 2.2 is calibrated for low CFG, never above 5.0)

### Anime Style LoRA (Recommended)

Two strong options for Wan 2.2 I2V on CivitAI. **A/B test both during Phase 1:**

**Option A -- Modern HD Anime (default recommendation):**
- **Model:** [Anime Style Wan 2.2 I2V](https://civitai.com/models/2222779/anime-style-wan-22-i2v) (Low Noise v2.0)
- **Trigger word:** `An1meStyl3`
- **Effect:** Flat cel-shaded textures, clean outlines, modern HD anime look
- **Weight:** Start at 0.7, adjust to taste

**Option B -- Retro 90s Anime (better Robotech style match):**
- **Model:** [Retro 90's Anime / Golden Boy Style](https://civitai.com/models/1671285/retro-90s-anime-golden-boy-style-lora-wan-22-14b)
- **Effect:** Trained on Wan 2.2 14B. Produces the hand-drawn, cel-painted look of 80s/90s anime. Robotech: New Generation (1985) and MOSPEADA share this visual era.
- **Weight:** Start at 0.6 (retro LoRAs tend to be more aggressive)
- **Why for Robotech:** The original Robotech animation has a specific 80s aesthetic -- warm film grain, ink outlines, watercolor-style backgrounds. This LoRA is closer to that look than the modern HD variant.

**Additional style LoRAs worth testing:**
- [Switch to Anime Style (I2V)](https://civitai.com/models/2222779) -- converts realistic inputs to anime
- [Hiro 2.5D](https://civitai.com/) -- hybrid semi-realistic anime, interesting for mecha detail

**LoRA stacking rules:** Style LoRAs before motion LoRAs in the chain. First LoRA has most influence. Max 3 LoRAs per job.

**Load in ComfyUI:** Add a LoRA Loader node between Load Diffusion Model and KSampler.

**Negative prompting for anime style:**
- Always add `((realistic))` and `((photograph))` to negative prompt to suppress photorealistic bias
- When combining with the anime LoRA: `(((realistic))), ((photograph)), live action, 3D render`

### Character Consistency Across Shots (Critical for Multi-Shot Production)

Ranked by effectiveness and complexity. Use techniques 1-3 for the initial production, graduate to 4-5 for polish.

| # | Technique | Complexity | Effectiveness | When to Use |
|---|-----------|-----------|---------------|-------------|
| 1 | **I2V chaining** | Low | Medium | Sequential shots of same subject. Use last frame of clip N as first frame of clip N+1. Works for slow motion; breaks on hard cuts. |
| 2 | **FLF2V (First-Last Frame)** | Low | High | Constrained transitions. Define both start and end frame, model interpolates. Forces pose/position consistency on short clips. Best for transformation shots (8, 15). |
| 3 | **Consistent ref image source** | Low | Medium-High | All shots. Process all reference images through the same style filter or generate all from the same AI model. Lock CLIP Vision settings across all shots. |
| 4 | **VACE ControlNet (Canny edge)** | Medium | **Very High** | Mecha shots. Extract Canny edge maps from concept art as structural control signals. Keeps silhouette locked while allowing surface animation. Mecha's hard geometric shapes respond especially well to Canny control. |
| 5 | **Character LoRA training** | High | **Very High** | If consistency is still lacking after techniques 1-4. Train a character LoRA on 15-30 reference images from multiple angles. Keep training under 1500-2000 steps to avoid overfit. |
| 6 | **Wan 2.6 R2V mode** | Medium | **Highest** | Future upgrade. Upload reference videos of the mecha in motion; model uses appearance + motion patterns from reference to maintain visual identity. Best option once Wan 2.6 ComfyUI integration matures. |

**VACE ControlNet setup for mecha:**
```
1. Render/extract concept art pose as Canny edge map
2. Add ControlNet node to workflow (VACE adapter for Wan 2.2)
3. Source image provides color/texture
4. Canny map provides structural constraint
5. Prompt provides motion and camera direction
```

Available via [Wan 2.1 Fun ControlNet](https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged) or **Wan2.2 VACE Fun** (updated Feb 2026). Supports depth (DepthAnything), Canny edge, DW Pose (skeletal), and combinable multi-condition workflows.

**VACE 1.3B Lightweight Option:** For structural previews, the VACE 1.3B model runs on **4-6GB VRAM** and achieves 17-22 FPS real-time streaming on consumer hardware. Use this for rapid iteration on pose/depth control signals before committing to the full 14B generation. The 1.3B model won't produce hero-quality output, but it validates composition and motion control in seconds rather than minutes. Install via [ali-vilab/VACE GitHub](https://github.com/ali-vilab/VACE).

**Mech-specific VACE technique:** VACE's flexible conditioning enables object-level masking -- you can overlay robotic/mecha textures on actor motion capture while preserving backgrounds. Combined with a mecha-style LoRA, this is the strongest pipeline for consistent mech animation. Particularly effective for transformation shots (8, 15) where precise structural control prevents the "melting" artifact.

### ComfyUI Settings Per Shot Type

| Shot Type | Resolution | Frames | Steps | CFG | Notes |
|-----------|-----------|--------|-------|-----|-------|
| Wide establishing | 832x480 | 81 | 20 | 3.5 | Minimal motion, dust/light |
| Character close-up | 480x832 (portrait) | 81 | 20 | 3.0 | Subtle motion only |
| Action/combat | 832x480 | 81 | 20 | 3.5 | Most motion, most regens |
| Transformation | 832x480 | 81 | 20 | 3.5 | Hardest shots - mechanical motion |
| Sky/flight | 832x480 | 81 | 20 | 3.5 | Fast motion, contrails |

---

## 6. Resource Estimates

### Time Budget (RTX 5080, 16GB VRAM)

| Phase | Time | Details |
|-------|------|---------|
| Reference image sourcing | 3-4 hours | Finding/creating 18 reference images |
| Image preparation | 1-2 hours | Cropping, cleaning, format standardization |
| VACE 1.3B structural previews (mecha shots) | ~15 min | ~1 min each for shots 8-9, 14-16 |
| LTX-2 motion previews (18 shots) | ~30 min | 10-15 sec each at NVFP4, quick pass |
| Wan 2.2 generation (18 shots x 2.5 avg attempts) | ~5-8 hours | 7-10 min per gen FP8, ~45 generations total |
| With SageAttention optimization | ~3-5 hours | ~4-5 min per gen |
| With Wan2GP + NV FP4 optimization | **~2.5-4 hours** | ~3-4 min per gen (best case) |
| Review and selection | 1-2 hours | Watching outputs, picking best takes |
| Post-processing (upscale + assembly) | 2-3 hours | Video2X upscale, RIFE interpolation, color grading, audio |
| **Total (FP8 baseline)** | **~13-20 hours** | Spread across multiple sessions |
| **Total (with SageAttention)** | **~10-15 hours** | Recommended path |
| **Total (with Wan2GP + NV FP4)** | **~9-13 hours** | Best case (requires PyTorch 2.9.1) |

**Generation time derivation (RTX 5080, Wan 2.2 FP8, 480p/81 frames/20 steps):**
- RTX 4090 reference: ~7-9 min at FP8 (from 33-frame benchmarks extrapolated to 81 frames)
- RTX 5080 vs 4090: roughly at parity for diffusion workloads (similar bandwidth: 960 vs 1008 GB/s)
- RTX 5080 FP8 central estimate: **7-10 min** per clip (no offloading), **12-15 min** if VRAM pressure triggers CPU offload
- With SageAttention: ~2.3x speedup = **~4-5 min** per clip
- With Wan2GP + NV FP4: additional ~30% faster = **~3-4 min** per clip (requires PyTorch 2.9.1 + CUDA 13)
- Key constraint: 16GB VRAM is the binding limit. FP8 is not optional -- it's the minimum for in-VRAM inference

**Full Model Speed Comparison (RTX 5080, 480p, ~4-5s clip):**

| Model | Precision | Gen Time | VRAM | Best For |
|-------|-----------|----------|------|----------|
| LTX-2 | NVFP4 | ~10-15 sec | ~6-8 GB | Previs, fast iteration |
| LTX-2 | NVFP8 | ~20-30 sec | ~8-10 GB | Previs |
| HunyuanVideo 1.5 | FP8 step-distilled | ~60-90 sec | ~12-14 GB | Quick quality clips |
| Wan 2.2 14B | FP8 + Wan2GP | ~3-4 min | ~14-16 GB | Fastest hero quality |
| Wan 2.2 14B | FP8 + SageAttention | ~4-5 min | ~14-16 GB | Hero quality |
| Wan 2.2 14B | FP8 baseline | ~7-10 min | ~14-16 GB | Hero quality (no optimizers) |
| VACE 1.3B | FP16 | ~1-3 min | ~4-6 GB | Structural control previews |
| VACE 14B | Quantized | ~10-15 min | ~14-16 GB | Full ControlNet hero shots |

### VRAM Budget

| Component | VRAM Usage |
|-----------|-----------|
| Wan 2.2 I2V active expert (FP8) | ~14.3 GB |
| Text encoder (UMT5-XXL FP8) | Offloaded to RAM between sampling |
| CLIP Vision encoder | ~1.7 GB (loaded during conditioning, then offloaded) |
| VAE decode | ~2 GB (loaded after sampling) |
| **Peak during sampling** | **~14.5 GB** (fits 16GB) |
| **System RAM required** | **~28 GB** (inactive expert + text encoder in RAM) |

### Disk Space

| Item | Size |
|------|------|
| Wan 2.2 models (already spec'd in setup guide) | ~37 GB |
| HunyuanVideo models (optional backup) | ~19 GB |
| LTX-2 (optional previews) | ~12 GB |
| Generated output (~45 clips x ~50MB) | ~2.3 GB |
| Reference images (18 x ~5MB avg) | ~90 MB |
| **Total new disk usage** | **~37-70 GB** |

### RTX 5080 Specific Performance Notes

The RTX 5080 has 16GB GDDR7 at 960 GB/s bandwidth with 450 AI TOPS (vs 5090's 838 TOPS, ~54% throughput). Key benchmarks:
- FP8 inference roughly at parity with RTX 4090 for diffusion workloads
- NVFP4 (LTX-2 exclusive) is ~2-3x faster than FP8 on Blackwell architecture
- 14B-class models (Wan 2.2's active expert at FP8) are ~14.3GB -- fits 16GB but with minimal headroom
- Model offloading to system RAM is smooth -- expert swap takes ~2-3 seconds
- NVFP4 software support for general diffusion is still maturing (NVIDIA demos ahead of third-party tools as of March 2026)
- FP8 is the sweet spot for quality/speed/VRAM on RTX 5080 right now

### SageAttention Optimization (Recommended)

```powershell
# Install SageAttention for 2.3x speedup on RTX 5080
pip install sageattention

# Launch ComfyUI with SageAttention enabled
python main.py --use-sage-attention
```

This cuts per-shot generation from ~12 min to ~5-6 min. The total generation phase drops from 8-12 hours to 4-6 hours.

### Alternative: GGUF Quantization for Speed/Headroom

If SageAttention isn't available or you want 720p:
```powershell
# Download GGUF Q4_K models (smaller, faster, slightly lower quality)
huggingface-cli download bullerwins/Wan2.2-I2V-A14B-GGUF --include "*.Q4_K_M.gguf" --local-dir ComfyUI/models/diffusion_models/
```
- Q4_K: ~6-8GB VRAM, enables 720p generation with headroom
- Q8: ~10-12GB VRAM, near-FP8 quality
- Requires ComfyUI-GGUF custom node installed

---

## 7. Post-Production Pipeline

### Hybrid Upscale Pipeline: Wan 2.2 + LTX-2 (New Technique, Feb 2026)

A documented workflow that combines the strengths of both models:
1. **Generate at 480p with Wan 2.2** (best quality, anime style, character coherence)
2. **Feed output to LTX-2 as upscaler/refiner** to reach 1440p+ with added detail
3. **Optimal denoising for refiner stage:** 0.6
4. **Works well for:** slow motion, establishing shots, static subjects
5. **Breaks down on:** high-motion sequences (action combat shots)

Use selectively: Shots 1, 3, 5, 7, 13, 18 (lower motion) are good candidates. Shots 8-12, 14-16 (high action) should stay at native Wan 2.2 resolution and use traditional upscaling.

Source: [Wan 2.2 + LTX-2 hybrid workflow](https://aurelm.com/2026/02/28/wan-2-2-external-actors-ltx-2-upscaler-refiner-actor-reinforcement-in-comfyui/)

### Traditional Upscale Pipeline: Video2X + Real-ESRGAN + RIFE (For High-Motion Shots)

For shots where the hybrid Wan+LTX-2 approach breaks down (action combat shots 8-12, 14-16):

**Step 1 -- Spatial Upscale (480p to 1080p):**
- **Tool:** [Video2X v6.0.0](https://github.com/k4yt3x/video2x) (complete C/C++ rewrite, GPU-accelerated)
- **Model:** `realesr-animevideov3` -- purpose-built for anime/vector/stylized content. Fastest and most accurate for cel-shaded animation.
- **Alternative:** `Real-CUGAN` for heavily compressed source material
- **Speed:** 1-5 FPS processing. A 5-second clip (80 frames at 16fps) upscaled to 1080p takes ~15-80 seconds on RTX 5080.

**Step 2 -- Frame Interpolation (16fps to 24fps):**
- **Tool:** RIFE (Real-Time Intermediate Flow Estimation) via Video2X or standalone
- **Effect:** Doubles framerate from 16fps native to 32fps, then trim to 24fps for smooth playback
- **Caution:** Anime-specific RIFE models exist and handle hard cuts between frames better than general-purpose models. Use these for cel-shaded content.

**Combined command (Video2X):**
```bash
video2x -i input_480p.mp4 -o output_1080p.mp4 -f realesr-animevideov3 -r 2 -m rife -t 24
```

**NVIDIA RTX Video Super Resolution** is also available as a driver-level feature (free, real-time during playback) but doesn't produce exportable output. Use for preview only.

### Assembly Tools
- **Video editor:** DaVinci Resolve (free) or CapCut
- **Upscaling:** Wan 2.2 + LTX-2 hybrid (low-motion shots) OR Video2X + realesr-animevideov3 (high-motion shots)
- **Frame interpolation:** RIFE via Video2X (16fps native to 24fps)
- **Audio:** Stock music + sound effects (freesound.org, epidemic sound). LTX-2 scratch audio for SFX reference.

### Assembly Order
1. Import all accepted clips into timeline
2. Trim to exact cut points (remove first/last frames if artifacts)
3. Add crossfade transitions between shots (0.5s dissolves for scene changes, hard cuts for action)
4. Color grade for consistency across shots
5. Add sound design: ambient (ruins), mecha SFX, weapon fire, Invid screeches, Alpha engine
6. Add music: build tension in Act 1-2, peak in Act 3-4, resolve in Act 5
7. Optional: add title card and end card

### Target Output
- **Resolution:** 832x480 (native) or upscaled to 1080p via Video2X + realesr-animevideov3
- **Framerate:** 16fps (Wan native) or interpolated to 24fps with RIFE via Video2X
- **Format:** MP4 H.264
- **Duration:** 60-90 seconds
- **Post-processing command:**
```bash
# Upscale + interpolate in one pass
video2x -i shot_XX_480p.mp4 -o shot_XX_1080p_24fps.mp4 -f realesr-animevideov3 -r 2 -m rife -t 24
```

---

## 8. Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| Mecha transformation looks melted/distorted | High - key shots ruined | Use clearest possible ref images mid-transform. Generate multiple seeds. Consider splitting transformation into 2-3 shorter clips stitched together. |
| Invid organic movement looks too human/wrong | Medium | Source Invid screencaps directly from the anime. Their jerky, insectoid motion actually works well with I2V artifacts. |
| Inconsistent character design across shots | High - breaks immersion | Use the same base reference images processed identically. Lock CLIP Vision settings. Consider building a LoRA (advanced, future). |
| VRAM OOM during generation | Medium - slows pipeline | Start at 480p. Use GGUF Q4 as fallback. Ensure 32GB RAM for model offloading. Close all other GPU apps. |
| 16fps output looks choppy | Low - solvable in post | Interpolate to 24fps with RIFE in ComfyUI or as post-process step. |
| Reference images too different in style | High - inconsistent look | Process all ref images through same style filter. Or generate all refs with same AI model (Flux or Seedream). |

---

## 9. Execution Phases

### Phase 0: Environment Validation (30 min)
- [ ] Run `validate_comfyui_env.py` on gaming PC
- [ ] Confirm Wan 2.2 models downloaded (per COMFYUI_VIDEO_SETUP.md Phase B)
- [ ] Import workflow JSON, verify all nodes load
- [ ] Install SageAttention: `pip install sageattention` for 2.3x speedup
- [ ] (Optional) Install Wan2GP: `git clone https://github.com/deepbeepmeep/Wan2GP` for NV FP4 30%+ speedup (requires PyTorch 2.9.1 / CUDA 13)
- [ ] Download BOTH anime LoRAs from CivitAI for A/B testing:
  - [Anime Style I2V v2.0](https://civitai.com/models/2222779/anime-style-wan-22-i2v) (modern HD)
  - [Retro 90's Anime / Golden Boy Style](https://civitai.com/models/1671285/retro-90s-anime-golden-boy-style-lora-wan-22-14b) (80s/90s look -- better Robotech match)
- [ ] Download VACE 1.3B for structural control previews: `git clone https://github.com/ali-vilab/VACE`
- [ ] Install Video2X for post-processing upscale: [github.com/k4yt3x/video2x](https://github.com/k4yt3x/video2x)

### Phase 1: Lower Decks POC (1-2 sessions, ~4-6 hours)
- [ ] Select 3-5 Lower Decks comic panels as reference images
- [ ] Generate test clips: talking head, walking, simple gesture
- [ ] **A/B test BOTH anime LoRAs** on the same reference image:
  - Modern HD LoRA at weights 0.5, 0.7, 0.9
  - Retro 90's LoRA at weights 0.4, 0.6, 0.8 (retro tends more aggressive)
  - Pick the winner for Phase 4 (or use different LoRAs for different shot types)
- [ ] Test negative prompt patterns (`((realistic))` suppression)
- [ ] Test I2V chaining: use last frame of clip 1 as input for clip 2
- [ ] Test VACE 1.3B for structural control on one simple shot (validate the pipeline)
- [ ] Iterate on prompt patterns, learn failure modes
- [ ] Document what works and what doesn't
- [ ] **Gate:** Can you reliably generate 5-second clips that look good? If no, stop here and iterate.

### Phase 1.5: Wan 2.6 Evaluation (Optional, 1 session, ~2 hours)
- [ ] Check Wan 2.6 ComfyUI integration status (may need ComfyUI-WanVideoWrapper update)
- [ ] Download Wan 2.6 I2V models if available in Comfy-Org repackaged format
- [ ] Test R2V mode with 2-3 Lower Decks character reference images
- [ ] Compare character consistency: Wan 2.2 I2V chaining vs Wan 2.6 R2V
- [ ] **Decision point:** If R2V consistency is significantly better, adopt Wan 2.6 for Phase 4
- [ ] Test multi-shot generation with "CUT TO" prompts (if available)

### Phase 2: Reference Library (1 session, ~4 hours)
- [ ] Source all 18 reference images (see Section 4)
- [ ] Prepare images: crop, clean, standardize format
- [ ] Organize in folder structure: `reference/shot_01/`, `reference/shot_02/`, etc.
- [ ] Generate Canny edge maps for mecha shots (8, 9, 14-16) for VACE ControlNet
- [ ] Optional: Generate missing refs with Flux/Seedream
- [ ] Process all images through same style filter for consistency

### Phase 3: Previs Pass with LTX-2 (1 session, ~2 hours)
- [ ] Run all 18 shots through LTX-2 at 540p for quick previews (~1-2 min each)
- [ ] Review: does the composition work? Does the motion make sense?
- [ ] Capture scratch audio from LTX-2 for SFX reference (Invid screeches, weapon fire, engines)
- [ ] Adjust reference images or prompts based on previews
- [ ] Lock the shot list -- no more changes after this point

### Phase 4: Hero Generation with Wan 2.2/2.6 (2-3 sessions, ~5-10 hours)
- [ ] Generate each shot with Wan 2.2 (or 2.6 if adopted) at 832x480 production settings
- [ ] Use anime LoRA at dialed-in weight from Phase 1
- [ ] Apply VACE ControlNet (Canny) for mecha-heavy shots (8, 9, 14-16)
- [ ] Use FLF2V for transformation shots (8, 15) -- constrain start and end frame
- [ ] 2-3 seeds per shot minimum, pick best
- [ ] Transformation shots (8, 15) may need 5+ attempts even with FLF2V
- [ ] Save all outputs organized by shot number
- [ ] Log prompt/seed/LoRA weight/ControlNet settings for each accepted take

### Phase 5: Post-Production (1 session, ~3-4 hours)
- [ ] Apply Wan 2.2 + LTX-2 hybrid upscale on low-motion shots (1, 3, 5, 7, 13, 18)
- [ ] Apply traditional upscale (RTX VSR or Topaz) on high-motion shots
- [ ] Assemble in video editor (DaVinci Resolve)
- [ ] Color grade for consistency across all 18 shots
- [ ] Add SFX and music (use LTX-2 scratch audio as starting point)
- [ ] Frame rate: keep at 16fps native or interpolate to 24fps with RIFE
- [ ] Export final MP4 at 1080p

### Total Timeline: ~5-8 sessions across 2-3 weeks (casual pace)

---

## 10. File Organization

```
claudeclaw/
  docs/
    ROBOTECH_VIDEO_PRODUCTION_PLAN.md    # This file
    COMFYUI_VIDEO_SETUP.md               # Setup guide (existing)
    workflows/
      wan22_i2v_14b_fp8_480p.json        # Base workflow (existing)

Gaming PC:
  ComfyUI/
    output/
      robotech/
        shot_01/                          # All takes for shot 1
        shot_02/
        ...
        shot_18/
    reference/
      characters/
        scott_bernard_cvr3.png
        cyclone_vr052_bike.png
        cyclone_vr052_armor.png
        alpha_fighter_jet.png
        alpha_battloid.png
        invid_scout.png
        invid_trooper.png
      environments/
        ruined_city_01.png
        ruined_city_02.png
      compositions/
        shot_01_wide_ruins.png
        shot_02_cyclones_riding.png
        ...
    project/
      robotech_edit/                      # Video editor project files
        timeline.drp                      # DaVinci Resolve project
        audio/
        exports/
```

---

## Sources

### Model Documentation
- [Wan 2.2 GitHub (Official)](https://github.com/Wan-Video/Wan2.2)
- [Wan 2.2 ComfyUI Repackaged (Comfy-Org)](https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged)
- [Wan 2.2 I2V A14B GGUF (bullerwins)](https://huggingface.co/bullerwins/Wan2.2-I2V-A14B-GGUF)
- [Wan 2.2 MoE Architecture Explained (DeepLearning.AI)](https://www.deeplearning.ai/the-batch/alibabas-wan-2-2-video-models-adopt-a-new-architecture-to-sort-noisy-from-less-noisy-inputs/)
- [Wan 2.2 Explained (Vast.ai)](https://vast.ai/article/wan-2-2-explained-new-approach-ai-video-generation)
- [Wan 2.6 Multi-Shot + R2V (Atlas Cloud)](https://www.atlascloud.ai/blog/Wan-2-6-is-now-available-on-Atlas-Cloud-A-New-Standard-for-Long-Form-Multi-Shot-Video-Generation)
- [ComfyUI Official Wan 2.2 Tutorial](https://docs.comfy.org/tutorials/video/wan/wan2_2)
- [Wan 2.2 ComfyUI Examples](https://comfyanonymous.github.io/ComfyUI_examples/wan22/)
- [HunyuanVideo 1.5 (Tencent)](https://github.com/Tencent-Hunyuan/HunyuanVideo-1.5)
- [HunyuanVideo-I2V (Tencent)](https://github.com/Tencent-Hunyuan/HunyuanVideo-I2V)
- [HunyuanVideo 1.5 FP8 Distilled (CivitAI)](https://civitai.com/models/2146726/hunyuanvideo-15)
- [LTX-2 Official (Lightricks)](https://ltx.io/model/ltx-2)
- [LTX-2 HuggingFace](https://huggingface.co/Lightricks/LTX-2)
- [LTX-2 GitHub](https://github.com/Lightricks/LTX-2)
- [LTX-2 ComfyUI Plugin](https://github.com/Lightricks/ComfyUI-LTXVideo)

### Style & Consistency Techniques
- [Anime Style LoRA for Wan 2.2 I2V (CivitAI)](https://civitai.com/models/2222779/anime-style-wan-22-i2v)
- [Wan 2.2 Anime Style Video Workflow (ComfyUI.org)](https://comfyui.org/en/anime-style-video-magic-workflow-guide)
- [Wan 2.2 I2V Prompting Guide (wan-animate)](https://wan-animate.com/posts/how-to-use-i2v-prompting-wan-2-2-animate-guide)
- [Character Consistency with AI (ComfyUI.org)](https://comfyui.org/en/unlock-anime-style-characters-with-ai)
- [Wan 2.2 + LTX-2 Hybrid Upscale Pipeline](https://aurelm.com/2026/02/28/wan-2-2-external-actors-ltx-2-upscaler-refiner-actor-reinforcement-in-comfyui/)
- [LTX-2 NVFP4 vs NVFP8 Quality (WaveSpeed)](https://wavespeed.ai/blog/posts/blog-ltx-2-nvfp4-vs-nvfp8/)

### Hardware & Benchmarks
- [ComfyUI RTX 5080 Benchmark (2.3x with SageAttention)](https://www.nrgumnaicreation.com/comfyui-rtx-5080-benchmark-results.html)
- [RTX 5080/5090 AI Benchmarks (Puget Systems)](https://www.pugetsystems.com/labs/articles/nvidia-geforce-rtx-5090-amp-5080-ai-review/)
- [RTX 5080 vs 4090 for AI (bestgpusforai.com)](https://www.bestgpusforai.com/gpu-comparison/5080-vs-4090)
- [RTX 5090 vs 4090 I2V Real-World (Valdi)](https://www.valdi.ai/blog/rtx-5090-vs-4090-in-the-real-world-of-image-to-video-inference)
- [Wan 2.2 GPU Performance Testing (Instasd)](https://www.instasd.com/post/wan2-1-performance-testing-across-gpus)
- [Wan 2.2 VRAM Requirements Guide (Novita)](https://blogs.novita.ai/wan-2-2-vram-find-the-best-gpu-setup-for-deployment/)
- [NVIDIA RTX Accelerates 4K AI Video with LTX-2](https://blogs.nvidia.com/blog/rtx-ai-garage-ces-2026-open-models-video-generation/)
- [NVIDIA RTX LTX-2 + ComfyUI Guide](https://www.nvidia.com/en-us/geforce/news/rtx-ai-video-generation-guide/)
- [Wan2GP - Low VRAM AI Video Generator](https://github.com/deepbeepmeep/Wan2GP)

### Setup & Workflow Guides
- [How to Get ComfyUI Running on RTX 5080](https://blog.comfy.org/p/how-to-get-comfyui-running-on-your)
- [Wan 2.2 I2V GGUF Low VRAM Guide (Next Diffusion)](https://www.nextdiffusion.ai/tutorials/how-to-run-wan22-image-to-video-gguf-models-in-comfyui-low-vram)
- [Wan 2.2 I2V Step-by-Step (Civitai)](https://civitai.com/articles/18271/step-by-step-guide-series-comfyui-wan-22-img-to-video)
- [Wan 2.2 I2V Workflow Guide (ComfyUI Wiki)](https://comfyui-wiki.com/en/tutorial/advanced/video/wan2.2/wan2-2)
- [LTX-2 ComfyUI Configuration Guide (zimage.run)](https://zimage.run/blog/how-to-configure-ltx-2-in-comfyui)
- [Seedream 5.0 Lite Docs](https://docs.comfy.org/tutorials/partner-nodes/bytedance/seedream-5-lite)

### VACE ControlNet
- [VACE GitHub (ali-vilab)](https://github.com/ali-vilab/VACE)
- [VACE ControlNet Step-by-Step Guide (Civitai)](https://civitai.com/articles/15565/step-by-step-guide-series-wan-vace-controlnet)
- [ComfyUI Wan 2.1 VACE Examples](https://docs.comfy.org/tutorials/video/wan/vace)
- [VACE Dos and Don'ts (Runpod)](https://www.runpod.io/blog/the-dos-and-donts-of-vace)
- [Wan2.2 VACE Fun Released](https://www.patreon.com/posts/wan2-2-vace-fun-138834021)

### Upscaling & Post-Processing
- [Video2X v6.0.0 (GitHub)](https://github.com/k4yt3x/video2x)
- [Video2X Documentation](https://docs.video2x.org/)
- [RIFE Frame Interpolation](https://github.com/hzwer/ECCV2022-RIFE)
- [Real-ESRGAN Anime Video v3](https://github.com/xinntao/Real-ESRGAN)

### Optimization
- [Wan2GP - Low VRAM AI Video Generator (GitHub)](https://github.com/deepbeepmeep/Wan2GP)
- [SageAttention (GitHub)](https://github.com/thu-ml/SageAttention)

### Wan 2.6 / R2V
- [Wan 2.6 Developer Guide (fal.ai)](https://fal.ai/learn/devs/wan-26-developer-guide-mastering-next-generation-video-generation)
- [Wan 2.6 R2V Flash (WaveSpeedAI)](https://wavespeed.ai/blog/posts/introducing-alibaba-wan-2-6-reference-to-video-flash-on-wavespeedai/)

### Additional LoRAs
- [Retro 90's Anime / Golden Boy Style LoRA (Civitai)](https://civitai.com/models/1671285/retro-90s-anime-golden-boy-style-lora-wan-22-14b)
- [Anime LoRA Training Guide for Wan 2.2 (Civitai)](https://civitai.com/articles/20389/tazs-anime-style-lora-training-guide-for-wan-22-part-1-3)

### Robotech Reference
- [Robotech Mecha Database - New Generation](https://robotech.com/roboverse/mecha-database/category/new-generation)
- [Cyclone (Robotech Wiki)](https://robotech.fandom.com/wiki/Cyclone)
- [Alpha Fighter (Robotech Wiki)](https://robotech.fandom.com/wiki/Alpha_Fighter)
