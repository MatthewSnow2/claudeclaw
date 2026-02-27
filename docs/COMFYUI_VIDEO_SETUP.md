# ComfyUI Video Generation Setup Guide

**Target machine:** Gaming PC (Windows, RTX 5080 16GB, CUDA 12.8)
**Last updated:** 2026-02-27
**Purpose:** Image-to-video generation for Lower Decks animation POC and Robotech scenes

---

## 1. Current State (from PIPELINE.md)

### Already Installed
- [x] ComfyUI installed (Python 3.11, CUDA 12.8)
- [x] SVD xt (Stable Video Diffusion) -- 8.9GB
- [x] AnimateDiff v3 -- 1.56GB
- [x] SD 1.5 -- 3.97GB
- [x] Custom nodes: AnimateDiff-Evolved, VideoHelperSuite
- [x] Launch script: `start_comfyui.bat`

### What's Outdated
- SVD xt and AnimateDiff are now **legacy** for video gen. Wan 2.2 and HunyuanVideo have surpassed them in quality and consistency.
- SD 1.5 is still useful as a base for ControlNet/img2img but not for video.

---

## 2. Recommended Models

### Priority Order (for your use case: image-to-video from existing art)

| # | Model | Why | VRAM (16GB feasible?) |
|---|-------|-----|----------------------|
| 1 | **Wan 2.2 I2V 14B** | Best open-source I2V. Dual-expert MoE architecture (high-noise + low-noise models), excellent motion. Native ComfyUI support. | Yes -- FP8 (dual 14.3GB models, auto-offloaded) |
| 2 | **HunyuanVideo 1.5 I2V** | Strong alternative, good with stylized content. CFG-distilled variant = fast. Native ComfyUI support. | Yes -- FP8 (8.3GB single model) |
| 3 | **LTX-2** | NVIDIA-optimized, NVFP4 support on RTX 5080. Fastest generation. | Yes -- built for 16GB |
| 4 | **Seedream 5.0 Lite** | Cloud/API only (BytePlus). Not local. Good for image gen, not video. | N/A (cloud) |

> **Seedream 5.0 Lite note:** This is **not a local model**. It runs via BytePlus API through ComfyUI Partner Nodes. Requires account login and API access. Good for image generation but not video. Skip for the video pipeline -- use it separately if you want high-quality reference image generation.

---

## 3. Setup Checklist

### Step 0: Verify ComfyUI is Current

```powershell
# In ComfyUI directory
git pull
pip install -r requirements.txt --upgrade
```

**Critical for RTX 5080:** You need PyTorch built against CUDA 12.8+. If ComfyUI was installed with the portable package v0.3.30+, you're good. Otherwise:

```powershell
pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
```

Verify: NVIDIA driver 570+ required. Check with `nvidia-smi`.

### Step 1: Install ComfyUI Manager (if not already installed)

```powershell
cd ComfyUI/custom_nodes
git clone https://github.com/ltdrdata/ComfyUI-Manager.git
```

Restart ComfyUI. Manager appears in the menu bar.

---

### Step 2: Download Wan 2.2 I2V Models (Priority 1)

Wan 2.2 uses a **Mixture of Experts** architecture with TWO separate diffusion models:
- **High-noise expert** -- handles initial structure/composition (denoising steps 0-10)
- **Low-noise expert** -- handles detail/refinement (denoising steps 10-20)

Both models are required. Only one is active in VRAM at a time (ComfyUI auto-offloads the other to system RAM).

#### Models to Download

All files from **[Comfy-Org/Wan_2.2_ComfyUI_Repackaged](https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/tree/main/split_files)**:

| File | Size | Destination |
|------|------|-------------|
| `wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors` | 14.3 GB | `ComfyUI/models/diffusion_models/` |
| `wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors` | 14.3 GB | `ComfyUI/models/diffusion_models/` |
| `umt5_xxl_fp8_e4m3fn_scaled.safetensors` | 6.74 GB | `ComfyUI/models/text_encoders/` |
| `wan_2.1_vae.safetensors` | 254 MB | `ComfyUI/models/vae/` |

CLIP Vision from **[Comfy-Org/Wan_2.1_ComfyUI_repackaged](https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/tree/main/split_files/clip_vision)**:

| File | Size | Destination |
|------|------|-------------|
| `clip_vision_h.safetensors` | ~1.7 GB | `ComfyUI/models/clip_vision/` |

**Total download: ~37 GB**

> **Important:** The 14B I2V models use `wan_2.1_vae.safetensors` (254 MB), NOT `wan2.2_vae.safetensors` (1.41 GB). The 2.2 VAE is for the 5B models only.

#### Direct Download URLs

```powershell
# Using huggingface-cli (recommended -- supports resume)
pip install huggingface-hub

# Diffusion models
huggingface-cli download Comfy-Org/Wan_2.2_ComfyUI_Repackaged split_files/diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors --local-dir ComfyUI/models/
huggingface-cli download Comfy-Org/Wan_2.2_ComfyUI_Repackaged split_files/diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors --local-dir ComfyUI/models/

# Text encoder
huggingface-cli download Comfy-Org/Wan_2.2_ComfyUI_Repackaged split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors --local-dir ComfyUI/models/

# VAE
huggingface-cli download Comfy-Org/Wan_2.2_ComfyUI_Repackaged split_files/vae/wan_2.1_vae.safetensors --local-dir ComfyUI/models/

# CLIP Vision (from 2.1 repo -- shared)
huggingface-cli download Comfy-Org/Wan_2.1_ComfyUI_repackaged split_files/clip_vision/clip_vision_h.safetensors --local-dir ComfyUI/models/
```

After download, move files from `split_files/` subdirs into the correct `ComfyUI/models/` subdirectories, or use symlinks.

#### Alternative: Browser Download

Direct browser links (right-click > Save As):
- https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors
- https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors
- https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors
- https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors
- https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/clip_vision/clip_vision_h.safetensors

#### Custom Nodes Needed
- **ComfyUI-VideoHelperSuite** -- already installed (for VHS_VideoCombine output node)
- **ComfyUI-GGUF** (only if using GGUF quantized models): Install via Manager or `git clone https://github.com/city96/ComfyUI-GGUF.git` into `custom_nodes/`

> Wan 2.2 I2V is **natively supported** in ComfyUI -- no custom wrapper needed. The built-in `Load Diffusion Model`, `Wan22ImageToVideoLatent`, and standard KSampler nodes handle everything.

#### Optional: Kijai's WanVideoWrapper (Advanced Features)

If you need block swapping, attention caching, torch.compile, or GGUF support:
```powershell
cd ComfyUI/custom_nodes
git clone https://github.com/kijai/ComfyUI-WanVideoWrapper
pip install -r ComfyUI-WanVideoWrapper/requirements.txt
```

Not needed for basic I2V. Start with native nodes first.

---

### Step 3: Download HunyuanVideo 1.5 I2V Models (Priority 2)

All files from **[Comfy-Org/HunyuanVideo_1.5_repackaged](https://huggingface.co/Comfy-Org/HunyuanVideo_1.5_repackaged/tree/main/split_files)**:

| File | Size | Destination |
|------|------|-------------|
| `hunyuanvideo1.5_480p_i2v_cfg_distilled_fp8_scaled.safetensors` | 8.33 GB | `ComfyUI/models/diffusion_models/` |

Supporting models from **[Comfy-Org/HunyuanVideo_repackaged](https://huggingface.co/Comfy-Org/HunyuanVideo_repackaged)**:

| File | Size | Destination |
|------|------|-------------|
| `clip_l.safetensors` | ~250 MB | `ComfyUI/models/text_encoders/` |
| `llava_llama3_fp8_scaled.safetensors` | ~8 GB | `ComfyUI/models/text_encoders/` |
| `llava_llama3_vision.safetensors` | ~1.7 GB | `ComfyUI/models/clip_vision/` |
| `hunyuan_video_vae_bf16.safetensors` | ~250 MB | `ComfyUI/models/vae/` |

**Total download: ~19 GB**

> Use the **480p cfg_distilled FP8** variant -- it's the fastest and fits 16GB VRAM comfortably. The cfg-distilled version requires fewer steps (fewer than 20 vs 50+ for non-distilled).

#### Custom Nodes
- Native ComfyUI support (v0.3.10+) -- no wrapper needed
- OR **ComfyUI-HunyuanVideoWrapper** (kijai) for advanced features: `git clone https://github.com/kijai/ComfyUI-HunyuanVideoWrapper.git` into `custom_nodes/`

#### 16GB VRAM Tips for HunyuanVideo
- Use FP8 weight_dtype in the Load Diffusion Model node
- Enable CPU offloading for text encoder (moves ~5GB to system RAM)
- Enable VAE tiling (saves 4-6GB VRAM, adds ~15% decode time)

---

### Step 4: Download LTX-2 (Priority 3 -- NVIDIA Optimized)

LTX-2 from Lightricks is specifically optimized for RTX 50-series via NVFP4/NVFP8. Fastest generation times on your hardware.

| File | Size | Destination | Source |
|------|------|-------------|--------|
| `ltx-video-2b-v0.9.5.safetensors` | ~4GB | `ComfyUI/models/diffusion_models/` | [HuggingFace: Lightricks/LTX-Video](https://huggingface.co/Lightricks/LTX-Video) |
| T5 text encoder | ~8GB | `ComfyUI/models/text_encoders/` | (may share with other models) |

> LTX-2 is very lightweight. On RTX 5080 with NVFP4: 540p, 4-second clips in under a minute.

---

### Step 5: Seedream 5.0 Lite (Optional -- Cloud API, Not for Video)

**This is NOT a local model.** It runs on BytePlus cloud infrastructure. Image generation only.

Skip for the video pipeline. If you want it later for reference image gen:
1. Update ComfyUI to latest nightly
2. Log into ComfyUI account (required for Partner Nodes)
3. Access via Partner Nodes section in ComfyUI

---

## 4. VRAM Budget (RTX 5080 -- 16GB)

| Model | Precision | Peak VRAM | Recommended Settings |
|-------|-----------|-----------|---------------------|
| Wan 2.2 I2V 14B | FP8 | ~14.3GB (one expert active) | 832x480, 81 frames (~5s at 16fps), dual KSampler |
| Wan 2.2 I2V 14B | GGUF Q8 | ~10-12GB | 480p-720p, 81 frames |
| Wan 2.2 I2V 14B | GGUF Q4 | ~6-8GB | 720p, 81 frames |
| HunyuanVideo 1.5 I2V | FP8 (cfg-distilled) | ~8-10GB | 832x480, 49 frames, CPU offload text encoder |
| HunyuanVideo 1.5 I2V | GGUF Q4 | ~6-8GB | 720p, enable VAE tiling |
| LTX-2 | NVFP4 | ~4-6GB | 540p, 4s clips, fastest option |
| SVD xt (existing/legacy) | BF16 | ~8-10GB | 576x1024, 25 frames |

**How Wan 2.2 Dual-Expert VRAM works:**
- Only ONE 14.3GB diffusion model is in VRAM at a time
- ComfyUI automatically offloads the inactive model to system RAM
- During KSampler #1 (steps 0-10): high-noise model in VRAM
- During KSampler #2 (steps 10-20): low-noise model swaps in, high-noise goes to RAM
- This means you need ~32GB system RAM minimum (14.3GB model in RAM + OS + ComfyUI overhead)

**Strategy for 16GB VRAM:**
- Use FP8 for quality (the default recommendation)
- Use GGUF Q4 if you want to try 720p or have VRAM pressure
- Ensure 32GB+ system RAM for smooth model offloading
- Close other GPU apps during generation
- Start at 480p to validate workflow, then try 720p if headroom exists

---

## 5. Wan 2.2 I2V Workflow (Complete Node Graph)

### Architecture: Dual-Expert Sampling

Wan 2.2 14B I2V uses two specialized diffusion models that process sequentially:
1. **High-noise expert** (KSampler #1, steps 0-10): Establishes structure and composition
2. **Low-noise expert** (KSampler #2, steps 10-20): Refines details and motion quality

This produces higher quality than a single model because each expert is specialized for its denoising range.

### Node List (13 nodes total)

```
NODE 1: Load Image
   - Upload a reference image (first frame of the video)
   - Outputs: IMAGE

NODE 2: Load Diffusion Model (High Noise)
   - unet_name: wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors
   - weight_dtype: fp8_e4m3fn_fast
   - Outputs: MODEL

NODE 3: Load Diffusion Model (Low Noise)
   - unet_name: wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors
   - weight_dtype: fp8_e4m3fn_fast
   - Outputs: MODEL

NODE 4: Load CLIP (Text Encoder)
   - clip_name: umt5_xxl_fp8_e4m3fn_scaled.safetensors
   - type: wan
   - Outputs: CLIP

NODE 5: Load VAE
   - vae_name: wan_2.1_vae.safetensors
   - Outputs: VAE

NODE 6: Load CLIP Vision
   - clip_name: clip_vision_h.safetensors
   - Outputs: CLIP_VISION

NODE 7: CLIP Text Encode (Positive Prompt)
   - text: "Character turns head and speaks, smooth animated motion,
           consistent art style, high quality"
   - clip: from NODE 4
   - Outputs: CONDITIONING

NODE 8: CLIP Text Encode (Negative Prompt)
   - text: "blurry, distorted, low quality, static, morphing,
           deformed, flickering, jittery"
   - clip: from NODE 4
   - Outputs: CONDITIONING

NODE 9: CLIP Vision Encode
   - image: from NODE 1
   - clip_vision: from NODE 6
   - Outputs: CLIP_VISION_OUTPUT (merged into positive conditioning)

NODE 10: Wan22ImageToVideoLatent
   - image: from NODE 1
   - width: 832
   - height: 480
   - length: 81 (= 16fps x 5 seconds + 1)
   - batch_size: 1
   - Outputs: LATENT

NODE 11: KSampler (High Noise Phase)
   - model: from NODE 2 (high-noise expert)
   - positive: from NODE 7 + NODE 9 (text + vision conditioning)
   - negative: from NODE 8
   - latent_image: from NODE 10
   - seed: [random]
   - steps: 20
   - cfg: 3.5
   - sampler_name: euler
   - scheduler: beta
   - start_at_step: 0
   - end_at_step: 10
   - return_with_leftover_noise: enable
   - add_noise: enable
   - Outputs: LATENT (partially denoised)

NODE 12: KSampler (Low Noise Phase)
   - model: from NODE 3 (low-noise expert)
   - positive: from NODE 7 + NODE 9 (same conditioning)
   - negative: from NODE 8
   - latent_image: from NODE 11 (output of first sampler)
   - seed: [same as NODE 11 -- keep fixed]
   - steps: 20
   - cfg: 3.5
   - sampler_name: euler
   - scheduler: beta
   - start_at_step: 10
   - end_at_step: 10000
   - return_with_leftover_noise: disable
   - add_noise: disable
   - Outputs: LATENT (fully denoised)

NODE 13: VAE Decode
   - samples: from NODE 12
   - vae: from NODE 5
   - Outputs: IMAGE (video frames)

NODE 14: VHS_VideoCombine (from VideoHelperSuite)
   - images: from NODE 13
   - frame_rate: 16
   - format: video/h264-mp4
   - filename_prefix: wan22_i2v
   - save_output: true
```

### Connection Map

```
Load Image ---------> CLIP Vision Encode -------> (merged into positive conditioning)
Load Image ---------> Wan22ImageToVideoLatent --> KSampler #1 --> KSampler #2 --> VAE Decode --> Save Video
Load CLIP ----------> CLIP Text Encode (pos) ---> KSampler #1 + #2
Load CLIP ----------> CLIP Text Encode (neg) ---> KSampler #1 + #2
Load CLIP Vision ----> CLIP Vision Encode
Load Diffusion #1 --> KSampler #1 (high noise, steps 0-10)
Load Diffusion #2 --> KSampler #2 (low noise, steps 10+)
Load VAE -----------> VAE Decode
```

### Quick Test Settings (minimize VRAM for first run)
- Resolution: 480x272 (in Wan22ImageToVideoLatent node: width=480, height=272)
- Frames: 41 (~2.5 seconds at 16fps)
- Steps: 20 (split 10/10 between samplers -- keep this, reducing further degrades quality)
- CFG: 3.5 (do NOT go above 5.0 -- Wan 2.2 is calibrated for low CFG)

### Production Settings (full quality)
- Resolution: 832x480
- Frames: 81 (~5 seconds at 16fps)
- Steps: 20 (split 10/10)
- CFG: 3.5
- Expected time: 5-15 minutes on RTX 5080

### Expected Output
- MP4 file in `ComfyUI/output/`
- The reference image appears as the first frame with generated motion continuing from it
- Wan default framerate is 16fps (not 24fps like traditional animation -- this is correct)

---

## 6. Importable Workflow

A ready-to-import ComfyUI workflow JSON is available at:

**`claudeclaw/docs/workflows/wan22_i2v_14b_fp8_480p.json`**

To use:
1. Open ComfyUI in browser
2. Drag and drop the JSON file onto the canvas, OR use Menu > Load
3. The workflow loads with all nodes pre-connected
4. Upload your source image to the "Load Image" node
5. Edit the positive prompt to describe desired motion
6. Click "Queue Prompt"

> You can also access the built-in template via Workflow > Browse Templates > Video > "Wan2.2 14B I2V" in recent ComfyUI versions.

---

## 7. Download Size Summary

| Model Package | Total Download | Priority |
|---------------|---------------|----------|
| Wan 2.2 I2V 14B (FP8 full set -- 5 files) | **~37 GB** | **Do first** |
| HunyuanVideo 1.5 I2V (FP8 cfg-distilled -- 5 files) | **~19 GB** | Second |
| LTX-2 | ~12GB | Third |
| Seedream 5.0 Lite | 0GB (cloud) | Skip for video |
| **Total (Wan + Hunyuan)** | **~56 GB** | -- |
| **Minimum viable (Wan 2.2 only)** | **~37 GB** | -- |

---

## 8. Execution Order on Gaming PC

Run these steps in order on the gaming PC.

**Pre-flight:** Run the validation script `scripts/validate_comfyui_env.py` from this repo (see `claudeclaw/scripts/validate_comfyui_env.py`). It checks NVIDIA driver, CUDA version, disk space, and model file presence.

### Phase A: Verify Base (30 min)
- [ ] Open ComfyUI, confirm it launches without errors
- [ ] Check `nvidia-smi` -- confirm CUDA 12.8, driver 570+
- [ ] Run ComfyUI Manager > Update All (get latest nodes)
- [ ] Verify PyTorch CUDA: in ComfyUI console, confirm `torch.version.cuda` shows 12.8+
- [ ] Confirm system RAM >= 32GB (needed for model offloading)

### Phase B: Download Wan 2.2 Models (1-3 hours depending on bandwidth)
- [ ] Install huggingface-cli: `pip install huggingface-hub`
- [ ] Download all 5 Wan 2.2 files (see Section 3, Step 2)
- [ ] Place in correct `ComfyUI/models/` subdirectories
- [ ] Restart ComfyUI
- [ ] Verify models appear in node dropdowns (Load Diffusion Model, Load CLIP, etc.)

### Phase C: Test Wan 2.2 I2V (30 min)
- [ ] Import workflow JSON (`wan22_i2v_14b_fp8_480p.json`) or build manually (Section 5)
- [ ] Upload a test image (Lower Decks panel recommended)
- [ ] First run: 480x272, 41 frames, 20 steps
- [ ] Verify output MP4 is generated in `ComfyUI/output/`
- [ ] If OOM: reduce frames to 25, or try GGUF Q4 models
- [ ] Second run: 832x480, 81 frames, 20 steps (production settings)

### Phase D: Download HunyuanVideo (1-2 hours)
- [ ] Download all 5 HunyuanVideo 1.5 files (see Section 3, Step 3)
- [ ] Test with a simple I2V workflow at 480p
- [ ] Compare output quality with Wan 2.2

### Phase E: LTX-2 Setup (Optional, 30 min)
- [ ] Download LTX-2 model
- [ ] Test with NVFP4 for maximum speed on RTX 5080
- [ ] Good for quick iteration / previews before running full quality on Wan/Hunyuan

---

## 9. Tips for Your Use Cases

### Lower Decks Animation (POC -- do this first)
- Source images: existing comic panels (consistent style = easier for I2V)
- Start with single panel, short motion (walking, talking, head turn)
- Wan 2.2 I2V at 480p is the sweet spot for iteration speed
- Keep prompts focused on motion, not style (the style comes from the source image)
- Example prompt: "Character turns head and speaks, animated TV show style, smooth motion"

### Robotech Scenes (Phase 2 -- after POC)
- More complex: multiple shots, mechanical animation (Cyclones, Alphas)
- Pull reference images from online first, build a reference library
- Storyboard the 15-20 shots before generating
- Mecha movement is harder for I2V -- expect more iteration
- Consider: generate each shot individually, composite in video editor

### General Tips
- I2V works best when the source image has clear composition and the subject is well-defined
- Avoid source images with lots of text or UI elements
- Start with 3-5 second clips, extend duration only after you're happy with the motion quality
- Wan 2.2 default is 16fps -- this is intentional, not a bug
- Save your workflows as JSON files for repeatability

---

## 10. Troubleshooting

| Issue | Fix |
|-------|-----|
| CUDA out of memory | Reduce resolution to 480x272, reduce frames to 41, use GGUF Q4, close other GPU apps |
| Model swap is slow | Ensure 32GB+ system RAM. Model offloading writes ~14GB to RAM between samplers |
| Black/corrupted output | Check VAE is `wan_2.1_vae.safetensors` (not wan2.2_vae), try different seed |
| No motion in output | Improve motion prompt, check CLIP Vision Encode is connected, ensure denoise=1.0 |
| Output is "cooked"/overexposed | CFG too high -- Wan 2.2 uses 2.0-4.0, never above 5.0 |
| Second KSampler produces noise | Ensure add_noise=disable on KSampler #2, return_with_leftover_noise=enable on #1 |
| Missing Wan22ImageToVideoLatent node | Update ComfyUI to latest version (git pull), it's a built-in node |
| ComfyUI won't start after update | Delete `__pycache__` in custom_nodes, reinstall torch for cu128 |
| Missing nodes in workflow | ComfyUI Manager > Install Missing Custom Nodes |
| RTX 5080 not detected | Update to NVIDIA driver 570+, ensure CUDA 12.8 toolkit |

---

## Sources

- [Comfy-Org/Wan_2.2_ComfyUI_Repackaged (HuggingFace)](https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged)
- [Wan 2.2 Diffusion Models](https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/tree/main/split_files/diffusion_models)
- [clip_vision_h.safetensors (Wan 2.1 shared)](https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/blob/main/split_files/clip_vision/clip_vision_h.safetensors)
- [ComfyUI Official Wan 2.2 Tutorial](https://docs.comfy.org/tutorials/video/wan/wan2_2)
- [Wan 2.2 ComfyUI Examples](https://comfyanonymous.github.io/ComfyUI_examples/wan22/)
- [kijai/ComfyUI-WanVideoWrapper](https://github.com/kijai/ComfyUI-WanVideoWrapper)
- [Wan 2.2 I2V FP8 Workflow Guide (NextDiffusion)](https://www.nextdiffusion.ai/tutorials/exploring-the-new-wan22-image-to-video-generation-model-in-comfyui)
- [Comfy-Org/HunyuanVideo_1.5_repackaged](https://huggingface.co/Comfy-Org/HunyuanVideo_1.5_repackaged)
- [HunyuanVideo I2V Guide (ComfyUI Wiki)](https://comfyui-wiki.com/en/tutorial/advanced/hunyuan-image-to-video-workflow-guide-and-example)
- [kijai/ComfyUI-HunyuanVideoWrapper](https://github.com/kijai/ComfyUI-HunyuanVideoWrapper)
- [ComfyUI Seedream 5.0 Lite Docs](https://docs.comfy.org/tutorials/partner-nodes/bytedance/seedream-5-lite)
- [NVIDIA RTX 5080 + ComfyUI Setup](https://blog.comfy.org/p/how-to-get-comfyui-running-on-your)
- [NVIDIA LTX-2 + ComfyUI Guide](https://www.nvidia.com/en-us/geforce/news/rtx-ai-video-generation-guide/)
- [Wan 2.2 GitHub](https://github.com/Wan-Video/Wan2.2)
- [Wan-AI/Wan2.2-I2V-A14B](https://huggingface.co/Wan-AI/Wan2.2-I2V-A14B)
