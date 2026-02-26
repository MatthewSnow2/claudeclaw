# Consolidated Campaign Plan: Beth/Ratchet Go-to-Market

**Date**: 2026-02-26
**Reviewers**: Market Researcher, Partnership Strategist, Campaign Architect, Healthcare Compliance Reviewer, Devil's Advocate

---

## Executive Summary

Ratchet addresses a real, quantified problem: home health nurses spend 40% of their time on documentation, driving burnout and 20-30% annual turnover. The market is $600M+ and growing. However, **Ratchet is not a product yet -- it is a prototype.** The current architecture (Claude Desktop + mock APIs + Windows) cannot reach nurses in the field, cannot touch real patient data, and cannot pass even basic healthcare vendor due diligence.

The specialist team produced excellent market intelligence, partnership strategies, and campaign plans. The Devil's Advocate correctly identified that all of this is premature until three prerequisites are met: (1) mobile delivery, (2) real EMR output (even copy-paste), and (3) minimum compliance posture.

**Recommendation**: Do NOT execute the full campaign. Instead, run a 2-week, sub-$500 validation sprint. If validation signals are positive, invest in a 90-day product rebuild. Marketing follows product, not the other way around.

---

## Cross-Reference: Where Specialists Agree and Disagree

| Topic | Market Research | Partnership | Campaign | Compliance | Devil's Advocate |
|-------|:-:|:-:|:-:|:-:|:-:|
| Market is real and large | Yes | Yes | Yes | Yes | Yes |
| HCHB is the right target | Yes | Yes | Yes | -- | No (too big, go direct-to-agency) |
| Product is ready for pilots | Implied yes | Implied yes | Yes | No (no PHI allowed) | No (fatal gap) |
| HIMSS 2026 is worth attending | -- | Yes | Maybe | -- | No (waste of money) |
| Compliance is manageable | -- | -- | -- | Yes (with $25-70K) | No (prohibitive pre-revenue) |
| 100:1 ROI is defensible | Yes | -- | Yes | -- | No (aspirational) |
| Mobile delivery is critical | -- | -- | Assumed | Implied | Yes (fatal without it) |

**Key contradiction**: Market Research marks "Works on Android: YES" in the gap analysis. This is false. Ratchet runs on Claude Desktop on Windows. The Devil's Advocate is correct that this is a fatal gap.

**Key agreement**: All 5 specialists agree the job-to-be-done is valid and the market is real. The disagreement is about timing, readiness, and M2AI's ability to capture it.

---

## Critical Findings Summary

### 3 Fatal Issues
1. **No mobile delivery** -- Nurses are in the field with tablets. Ratchet runs on Windows Claude Desktop.
2. **Mock APIs only** -- No real EMR read/write. A "pilot" with mock data is a demo.
3. **Architecture must be rebuilt** -- Claude Desktop can't touch PHI. Every layer of the stack changes for production.

### 5 Serious Issues
4. HCHB has no reason to partner with a one-person shop (yet)
5. $25-70K compliance investment before any real PHI
6. 4-5 funded competitors already in market with mobile apps and compliance
7. Campaign plan requires resources M2AI doesn't have (36 content pieces / 90 days + conferences + pilots)
8. Healthcare enterprise sales cycles are 6-18 months, not 90 days

### 2 Manageable Issues
9. ROI model needs grounding in defensible metrics (overtime reduction, not "time saved = money saved")
10. HIMSS 2026 is too soon -- target AHHC (April) or later conferences instead

---

## The Plan: Three Phases with Decision Gates

### Phase 0: Validate (This Week -- 2 Weeks, <$500)

**Goal**: Answer "should we even do this?" with data, not assumptions.

| # | Action | Cost | Time | What You Learn |
|---|--------|------|------|----------------|
| 1 | Talk to 5 home health nurses (Nashville, LinkedIn, Reddit) | $0 | 3-5 days | Do they want voice documentation? What form factor? What EMR? |
| 2 | Build a 30-min mobile web prototype (voice -> SOAP note, no EMR) | $0 | 3-5 days | Does the core value prop work on a phone? |
| 3 | Submit HCHB partner inquiry at hchb.com | $0 | 15 min | Starts the clock (60-day kill criterion) |
| 4 | Cold-message 3 nursing directors on LinkedIn (feedback request, not pitch) | $0 | 1-2 days | Will decision-makers even take a meeting? |
| 5 | 1-hour call with healthcare compliance consultant | $200-500 | 1 day | Real compliance costs vs desk research estimates |

**Decision gate**: Proceed to Phase 1 ONLY if:
- 3+ nurses confirm they'd use a mobile voice documentation tool
- 1+ nursing directors respond to outreach
- Mobile prototype generates a credible SOAP note from voice input

**Kill if**: 0 nurses interested, 0 directors respond, or compliance consultant says minimum viable is >$50K.

### Phase 1: Build the Real Product (Months 1-3, ~$15-25K)

Only start this after Phase 0 validation. Sequence: product first, compliance second, marketing third.

**Month 1: Mobile Web App**
- Rebuild Ratchet as a mobile web app (PWA) calling Anthropic API directly
- Voice capture -> transcription -> SOAP note generation -> display
- Output: copyable text formatted for paste into any EMR
- Deploy on Vercel (not Netlify -- no PHI, but better for API routes)
- Test with 3-5 Nashville nurses using de-identified scenarios

**Month 2: Compliance Foundation**
- Engage Anthropic enterprise sales for API BAA
- Upgrade Supabase to Team + HIPAA add-on ($949/mo)
- Draft HIPAA policies (Privacy, Security, Breach Notification)
- Implement audit logging and basic RBAC
- Get E&O insurance quote

**Month 3: Pilot Prep**
- 30-day mock-data pilot with 5-10 Nashville nurses
- Capture: time-per-note, notes-per-day, satisfaction scores, accuracy review
- Record 2-3 video testimonials (60-90 seconds, phone-shot)
- Build one ROI case study from pilot data

**Budget estimate**: $15-25K (engineering: $5-15K if contracted, compliance: $5-10K, Supabase HIPAA: ~$3K for 3 months)

**Decision gate**: Proceed to Phase 2 ONLY if:
- Pilot nurses use the tool voluntarily (not just when prompted)
- Average documentation time drops by >50%
- 0 critical accuracy errors in AI-generated notes
- At least 1 nurse says "I can't go back to the old way"

### Phase 2: Go to Market (Months 4-9, ~$20-40K)

Only start this with pilot data, testimonials, and minimum compliance.

**Months 4-5: Targeted Outreach**
- Attend AHHC conference (April 2026 -- if Phase 1 completes in time) or National Alliance Summer (July 2026)
- LinkedIn: 1 post/week, demo video, pilot results
- Direct outreach to 10 mid-size home health agencies (100-300 nurses)
- Pricing: $30-50/clinician/month (not $10 -- signal quality)
- Offer: 30-day paid pilot, $1/clinician/month trial rate

**Months 6-9: Scale**
- SOC 2 Type 1 process ($20-50K -- start if 2+ agencies in paid pilots)
- HCHB partner program application (with pilot data and traction)
- Expand to 3-5 agencies
- Hire part-time content marketer or use AI-assisted content pipeline
- Build ROI calculator for executive briefings

**Budget estimate**: $20-40K (conference: $3-5K, SOC 2: $20-50K, marketing: $5-10K)

**Decision gate**: Proceed to scale ONLY if:
- 2+ agencies in paid pilots
- Monthly recurring revenue covers Supabase + compliance costs
- HCHB responds to partner inquiry (or alternative EMR path validated)

---

## What NOT to Do Right Now

Based on Devil's Advocate findings and cross-referenced specialist reports:

1. **Do NOT go to HIMSS 2026** (March 9-12). No mobile product, no compliance, no case studies. Waste of $3-4K.
2. **Do NOT execute the 90-day content calendar**. 36 content pieces for a one-person shop with 4 other projects is not realistic.
3. **Do NOT pursue HCHB partnership as primary strategy**. File the inquiry, but lead with direct-to-agency. Prove the product works with real nurses first.
4. **Do NOT invest in compliance before validating product-market fit**. Demo with mock/synthetic data is compliant. Validate first, comply second.
5. **Do NOT claim "PointCare integration"** in any materials. Ratchet does not integrate with PointCare. It generates notes that can be copied into PointCare. Honest positioning builds trust.
6. **Do NOT price at $10/clinician/month**. Too low to be credible or sustainable. $30-50/month is the floor.

---

## Kill Criteria

Abandon Ratchet healthcare play and refocus on ST Metro / AI consultancy if ANY of these become true:

1. Phase 0 validation fails (0 nurse interest, 0 director responses)
2. HCHB rejects partner inquiry AND no alternative EMR path emerges within 90 days
3. Total spend exceeds $15K before any real nurse uses the product
4. Mobile web app not shippable within 90 days of starting Phase 1
5. Narrable or Roger Healthcare announces HCHB/PointCare-native integration
6. Consulting revenue drops >25% due to Ratchet time investment
7. After 6 months, <2 agencies in any form of pilot (paid or free)

---

## Budget Summary

| Phase | Timeline | Investment | Revenue Expected |
|-------|----------|------------|-----------------|
| Phase 0: Validate | 2 weeks | <$500 | $0 |
| Phase 1: Build | Months 1-3 | $15-25K | $0 |
| Phase 2: GTM | Months 4-9 | $20-40K | First revenue month 6-9 |
| **Total to revenue** | **6-9 months** | **$35-65K** | **Target: $3-5K MRR** |

At $40/clinician/month, 100 clinicians = $4,000 MRR. That's 2-3 mid-size agencies.

---

## Immediate Actions (This Week)

1. [ ] Talk to 2 home health nurses (Matthew's Nashville network, LinkedIn)
2. [ ] Build mobile web prototype: voice -> SOAP note (Vercel, Anthropic API, no EMR)
3. [ ] Submit HCHB partner inquiry form
4. [ ] Send 3 LinkedIn messages to nursing directors (feedback request)
5. [ ] Book 1 call with healthcare compliance consultant

**Total time commitment**: ~8-10 hours across the week
**Total cost**: $0-$500

---

## Files Produced

```
outputs/beth_ratchet_campaign/
  market_research.md          -- EMR market map, competitors, target orgs, sizing
  partnership_strategy.md     -- Decision-maker map, 5 outreach strategies, templates
  campaign_plan.md            -- Messaging, channels, 90-day calendar, conference strategy
  compliance_review.md        -- HIPAA, SOC 2, AI regs, table stakes, risk assessment
  devils_advocate.md          -- 10 objections, kill criteria, de-risk recommendations
  consolidated_campaign_plan.md -- This document (synthesized action plan)
  agent_team_prompt.md        -- The prompt that generated this analysis
```

---

*Consolidated by Data (Chief of Staff) on 2026-02-26. Based on outputs from 5 specialist agents reviewing market, partnership, campaign, compliance, and adversarial perspectives.*
