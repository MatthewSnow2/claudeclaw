# Beth/Ratchet Go-to-Market: Home Health EMR Market Research

**Date**: 2026-02-26
**Product**: Ratchet -- AI-powered MCP tool for voice-based home health documentation on PointCare EMR (HCHB)
**Demo**: https://pointcare-emr-demo.netlify.app

---

## 1. Home Health EMR Market Map

### Market Size & Growth

- **Home Healthcare Software Market**: $4.51B (2025), projected to reach $8.20B by 2030 (13% CAGR)
- **US Home Healthcare Market**: $162.35B (2024), projected to reach $381.40B by 2033 (10% CAGR)
- The market is growing fast, driven by aging demographics, hospital-at-home programs, and Medicare reimbursement shifts toward value-based care

### Key EMR Players in Home Health

| Vendor | Market Position | Key Stats | Notes |
|--------|----------------|-----------|-------|
| **Homecare Homebase (HCHB)** | #1 - Dominant leader | 43.8% home health market, 48% admin market share, 33.5% clinical market share. Serves all top 10 largest HH agencies. 300,000+ users, 121M+ annual visits | **This is Ratchet's target platform.** PointCare is HCHB's mobile field app. Owned by Hearst Health. |
| **WellSky** | #2-3 - Strong mid-market | Top usability scores per KLAS. Cloud-based. 20,000+ client sites. Partnership with Google for AI. | Launched WellSky Scribe (ambient AI) Oct 2025 -- direct competitor threat. |
| **MatrixCare** (ResMed/Brightree) | #2-3 - High satisfaction | Highest KLAS ratings. Strong in post-acute. | Part of ResMed's health technology portfolio. |
| **Netsmart Technologies** | #4 - Behavioral health crossover | 2.1% acute market share. 26 Black Book awards. Strong in behavioral health + home care. | Aveanna Healthcare uses Netsmart's myUnity Clinical. |
| **Axxess** | #5 - Fast-growing cloud player | 7,000-9,000 agencies, 250,000+ users, 1.5M+ patients. Cloud-native. | Targets small-to-mid agencies. 40+ integrations. |
| **Epic Systems** | Emerging in home care | Expanding from hospital into home health. | Large health systems pushing Epic into home care divisions. |
| **Alora Health** | Niche / SMB | Targets smaller agencies | Lower-cost option for independent agencies. |
| **CareVoyant** | Niche | Multi-service (HH, hospice, private duty) | Integrated platform for diversified home care. |

### Market Concentration

The top five vendors capture approximately 45% of annual sales. HCHB alone dominates the large-agency segment with nearly half the market. The market is moderately concentrated at the top but highly fragmented among smaller agencies.

### Key Trends

1. **AI integration** is now table stakes -- vendors embedding predictive models for staffing, risk identification, and documentation
2. **Cloud migration** accelerating; legacy on-prem solutions losing ground
3. **Interoperability** via FHIR/Carequality becoming a differentiator
4. **Consolidation** continuing through M&A (WellSky acquiring Bonafide, Hearst acquiring CellTrak)
5. **Ambient AI documentation** emerging as the hottest feature category (WellSky Scribe, HCHB partnerships)

---

## 2. PointCare / AccentCare / HCHB Organizational Intel

### Critical Clarification: The PointCare Relationship

**PointCare is NOT an AccentCare product. PointCare is HCHB's mobile clinical application.**

- PointCare is the Android-based mobile app that HCHB's 130,000+ field clinicians use for point-of-care documentation
- AccentCare is a *customer* of HCHB -- they use PointCare as their field documentation tool
- PointCare syncs clinical data back to the HCHB EMR backend (Start of Care visits sync in under 2 minutes)
- R2 is HCHB's back-office application (scheduling, billing, compliance)

**This means Ratchet's integration target is HCHB (the vendor), not AccentCare (a customer).**

### HCHB (Homecare Homebase) -- The Platform Owner

| Attribute | Detail |
|-----------|--------|
| **Parent Company** | Hearst Health (Hearst Corporation acquired 85% stake in Dec 2013) |
| **Hearst Health Portfolio** | FDB (First Databank), Zynx Health, MCG, HCHB, MHK |
| **Founded** | 1999, Dallas TX |
| **Employees** | ~1,500 (estimated) |
| **Users** | 300,000+ clinicians |
| **Patients Served** | ~1M daily, 800,000+ at any time |
| **Annual Visits** | 121M+ |
| **Market Share** | 43.8% home health, 38.7% hospice |
| **Top Clients** | All 10 of the top 10 largest HH agencies, 8 of top 10 hospice |
| **Key Products** | HCHB Platform (back office), PointCare (mobile clinical), CareManager (personal care), HCHB Connect (interoperability), HCHB Exchange (Carequality) |

### HCHB Partner Ecosystem & Integration

- **HCHB Connect Suite**: Interoperability platform connecting to 600,000+ healthcare providers, 40,000 clinics, 1,700 hospitals via Carequality/Surescripts
- **Partner Ecosystem**: Curated third-party vendors for clinical training, care optimization, coding
- **Custom Integration Services**: HCHB offers custom integration aligned with home health/hospice needs
- **No public API documented**: Integration appears to go through HCHB's partner program, not a self-serve developer API

**Partnership Decision-Makers at HCHB**: Product leadership, VP of Partnerships/Alliances, CTO. Hearst Health corporate may have influence on larger strategic deals.

### AccentCare -- A Key HCHB Customer

| Attribute | Detail |
|-----------|--------|
| **Parent Company** | Advent International (PE firm, acquired May 2019 from Oak Hill Capital) |
| **Revenue** | $2.2B - $6B (estimates vary by source) |
| **Employees** | 30,000+ |
| **Operations** | 260+ sites of care across 32 states |
| **Patients** | 200,000+ annually |
| **Services** | Home health, hospice, personal care, care management |
| **Market Position** | 6th largest home health platform, 3rd largest personal care platform in US |
| **EMR** | Uses HCHB (PointCare for field staff, R2 for back office) |
| **Subsidiaries** | Seasons Hospice & Palliative Care, Sta-Home, Gareda, HRS, Texas Home Health, Southeastern Health Care at Home, Guardian (all unified under AccentCare brand in 2022) |
| **Partners** | Works with 60+ health systems and physician practices |

### Recent HCHB News & Developments

- **2024 (Dec)**: HCHB announced year of growth, product innovation, and industry leadership
- **2025**: Samsung partnership for streamlined enterprise solutions in home health/hospice
- **2022**: Hearst acquired CellTrak (care documentation software) -- expanding mobile capabilities
- **2025-2026**: Active investment in AI features, interoperability, and cloud infrastructure

---

## 3. Target Organizations

### Tier 1: Large HCHB Customers (Known PointCare Users)

These are confirmed HCHB/PointCare users. Large enough to have budget, established vendor relationship with HCHB.

| # | Organization | Size (Employees) | Patients | States | HQ | EMR | Notes |
|---|-------------|-------------------|----------|--------|-----|-----|-------|
| 1 | **AccentCare** | 30,000+ | 200,000/yr | 32 | Dallas, TX | HCHB/PointCare | 6th largest HH platform. Advent International (PE) owned. |
| 2 | **Bayada Home Health Care** | 31,500 | Large | 23+ | Moorestown, NJ | HCHB | Nonprofit. $1.49B revenue. One of the largest. |
| 3 | **Amedisys** | 21,000+ | Large | 38 | Baton Rouge, LA | HCHB | $1.46B NPR. Publicly traded (AMED). |
| 4 | **Interim Healthcare** | 43,000 | Large | 40+ | Sunrise, FL | HCHB | $3B revenue. Franchise model. |
| 5 | **Encompass Health (Home Health)** | 10,000+ | Large | 36 | Birmingham, AL | HCHB | Publicly traded (EHC). Spun off from Encompass rehab. |
| 6 | **VNA Health Group** | 2,500+ | Moderate | NJ | Red Bank, NJ | HCHB | Nonprofit. $229M revenue. Good mid-size target. |

### Tier 2: Mid-Size Agencies (100-1,000 Nurses) -- Primary Ratchet Targets

These are the sweet spot: large enough to have budget and IT infrastructure, small enough to make decisions quickly.

| # | Organization | Size | HQ | EMR (if known) | Notes |
|---|-------------|------|-----|----------------|-------|
| 7 | **Pinnacle Home Care** | 1,000+ clinicians | FL | Likely HCHB | Major FL provider. Fast-growing. |
| 8 | **Five Star Home Health Care** | Mid-size | Various | HCHB (confirmed) | Announced HCHB adoption for scheduling/compliance. |
| 9 | **Graham Healthcare Group** | Mid-size | Washington, PA | Likely HCHB | Subsidiary of Graham Holdings. Multiple HH brands. |
| 10 | **Elara Caring** | 26,000 caregivers | Dallas, TX | Unknown | 60,000+ patients daily. 18 states. May be larger than ideal but worth targeting. |
| 11 | **Enhabit Home Health & Hospice** | 10,000+ | Dallas, TX | Unknown | 228,000+ patients/yr. 365 locations. 34 states. Publicly traded (EHAB). |
| 12 | **CenterWell Home Health** | Large | Atlanta, GA | Unknown | Formerly Kindred at Home. $1.49B NPR. Humana subsidiary. |
| 13 | **Compassus** | Mid-size | Brentwood, TN | Unknown | Home health + hospice + palliative. Growing footprint. |

### Tier 3: Non-HCHB Agencies (Potential Future Targets After EMR Expansion)

| # | Organization | Size | EMR | Notes |
|---|-------------|------|-----|-------|
| 14 | **Aveanna Healthcare** | 300+ locations, 33 states | Netsmart myUnity | 40,000+ patients. Would require Netsmart integration. |
| 15 | **Addus HomeCare** | Large | Unknown | Publicly traded (ADUS). Personal care + home health. |

### Targeting Strategy

**Start with Tier 1 (AccentCare, Bayada, Amedisys)** for validation and case studies, then go after **Tier 2 mid-size agencies** for faster sales cycles. The HCHB connection is the common thread -- every agency using PointCare is a potential Ratchet customer.

---

## 4. Competitor Analysis: AI Documentation in Healthcare

### Market Overview

The ambient clinical documentation market generated **$600M in revenue in 2025** (2.4x YoY increase), making it healthcare AI's first breakout category. Projected to reach **$17.75B by 2033** (28.7% CAGR).

### Major Players

| Vendor | Focus | Pricing | Funding | Market Share | Home Health? | Key Differentiator |
|--------|-------|---------|---------|-------------|--------------|-------------------|
| **Nuance DAX Copilot** (Microsoft) | Enterprise hospitals | Custom/enterprise | Microsoft-backed | 33% of ambient market | No -- hospital/clinic focused | Deep Epic integration. Massive install base. Microsoft distribution. |
| **Abridge** | Enterprise health systems | ~$208-250/mo/clinician | $250M Series D ($2.75B valuation, Feb 2025) | 30% of ambient market | No -- acute/ambulatory | 150+ health system contracts. Epic Haiku/Canto integration. Sub-2-min note delivery. |
| **Ambience Healthcare** | Health systems | Enterprise pricing | Well-funded | 13% of ambient market | No -- acute care | Full-stack approach: documentation + coding + orders. |
| **Suki AI** | Multi-specialty | $399/mo/clinician | $70M Series D | Growing | No -- physician-focused | Goes beyond documentation: dictation, ICD-10/HCC, Q&A, order staging. |
| **DeepScribe** | Specialty practices | ~$750/mo/clinician | Funded | Niche | No -- specialty clinics | Deep specialty focus. High accuracy. Premium pricing. |
| **Nabla** | Primary care | $119/mo/clinician | $24M Series B | Growing | No -- primary care | Lower price point. Good for smaller practices. |
| **Freed AI** | Independent practices | Low-cost | Growing | Large indie base | No -- small practices | Free tier available. Consumer-style UX. |

### Home Health-Specific AI Documentation Solutions

**This is where the gap exists.** Very few solutions target home health specifically:

| Vendor | Focus | Status | Notes |
|--------|-------|--------|-------|
| **WellSky Scribe** | Home health ambient AI | Launched Oct 2025 | Only works within WellSky EHR. Google partnership. 50% documentation time reduction. Also launching WILA (voice assistant for OASIS). **Biggest competitive threat.** |
| **Narrable Health** | Home health ambient AI | Active | Purpose-built for Medicare-certified HH agencies. Focuses on OASIS SOC, evaluations, routine visits. Claims 30-40 min time savings. EHR-agnostic (FHIR, browser extension, copy-paste). 85% documentation time reduction in pilots. |
| **nVoq** | Home health voice/ambient | Established | Speech-to-text + ambient Voice Assistant. HIPAA/SOC2. Specialized language models for home health/hospice. Android mobile app. Integrates with multiple HH EMRs. Older technology base. |
| **OrbDoc** | Home health + rural | Active | Only offline-capable ambient solution. Good for areas with poor connectivity. |

### Gap Analysis: What Ratchet Offers That Competitors Don't

| Capability | Ratchet | WellSky Scribe | Narrable | nVoq | Nuance/Abridge/Suki |
|-----------|---------|---------------|----------|------|---------------------|
| Built specifically for HCHB/PointCare | YES | No (WellSky only) | Partial (EHR-agnostic) | Partial | No |
| MCP-native architecture | YES | No | No | No | No |
| Voice/natural language input | YES | Yes | Yes | Yes | Yes |
| OASIS-aware documentation | YES | Partial | Yes | Partial | No |
| Works on Android (field) | YES | WellSky mobile | Mobile-friendly | Yes (Android app) | Varies |
| HCHB PointCare integration | YES | No | Via workarounds | Possible | No |
| Home health-specific NLP | YES | Yes | Yes | Yes | No |
| Offline capability | TBD | Unknown | No | Yes (nVoq Mobile) | No |

### Ratchet's Competitive Moat

1. **HCHB/PointCare-native**: No competitor has deep PointCare integration. WellSky Scribe only works with WellSky. Narrable is EHR-agnostic but uses workarounds. Ratchet would be the first AI documentation tool built *into* the PointCare workflow.

2. **Market gap at #1 EMR**: HCHB controls 43.8% of home health and has NO native ambient AI documentation product. WellSky (their competitor) launched Scribe in Oct 2025. HCHB customers are watching WellSky agencies get this capability and they don't have it yet.

3. **MCP architecture**: Modern, extensible, tool-based architecture vs. monolithic competitors. Enables faster iteration and broader integration surface.

4. **Timing**: The ambient AI wave has proven product-market fit in acute care ($600M market, 2.4x YoY). Home health is 12-18 months behind but accelerating. First-mover advantage on the dominant platform is available now.

---

## 5. Market Sizing

### Total Addressable Market (TAM)

#### US Home Health Industry

| Metric | Value | Source |
|--------|-------|--------|
| Medicare-certified home health agencies | ~11,350 (2021, declining from peak of 12,459 in 2013) | CMS |
| Total home health agencies (all types) | ~33,200 (2022) | Industry estimates |
| Total home health professionals (RNs, aides, therapists) | 1.5M+ (2022) | BLS/Industry |
| Direct care workers (broader category) | 5M (2023, up from 3.5M in 2014) | Industry |
| US home healthcare market | $162.35B (2024) | Grand View Research |
| Home healthcare software market | $4.51B (2025) | Mordor Intelligence |

#### Documentation-Specific TAM

| Metric | Value | Calculation/Source |
|--------|-------|--------------------|
| Ambient clinical documentation market (all healthcare) | $600M (2025) | Menlo Ventures |
| Projected ambient documentation market | $17.75B by 2033 | Industry reports (28.7% CAGR) |
| Home health share of healthcare documentation | ~8-12% (estimated) | Based on visit volume ratios |
| **Estimated home health AI documentation TAM** | **$50-70M (2025), growing to $1.5-2B by 2033** | Proportional estimate |

#### HCHB-Specific SAM (Serviceable Addressable Market)

| Metric | Value | Calculation |
|--------|-------|-------------|
| HCHB users (field clinicians) | 300,000+ | HCHB stated |
| HCHB annual visits | 121M+ | HCHB stated |
| At $5-15/clinician/month (Ratchet pricing range) | **$18M - $54M/year ARR** | 300,000 x $5-15 x 12 |
| At $3-5/visit (per-visit pricing model) | **$363M - $605M/year** | 121M visits x $3-5 |
| Conservative: 10% penetration at $10/clinician/month | **$3.6M ARR** | 30,000 x $10 x 12 |
| Aggressive: 25% penetration at $10/clinician/month | **$9M ARR** | 75,000 x $10 x 12 |

### Documentation Burden Data

| Metric | Value | Source |
|--------|-------|--------|
| Nurse time spent on documentation | ~40% of shift | JAMIA/Oxford Academic |
| Average home health patients per nurse per day | 7 | Industry research |
| OASIS Start of Care assessment time | 57.3 minutes (CMS estimate) | CMS PRA Disclosure |
| Documentation time savings from ambient AI | 30-50% (30 min per visit) | WellSky Scribe, Narrable pilots |
| Data points documented per 12-hour shift | 600-800 (one per 1.11 minutes) | JAMIA research |
| After-hours charting | Common, significant contributor to burnout | Multiple sources |

### Nurse Turnover Economics

| Metric | Value | Source |
|--------|-------|--------|
| Average nurse turnover rate | 18.7% (2021, up from 16.8% in 2019) | Industry data |
| Home health nurse turnover | Higher than average (estimated 25-30%) | Timeero/Industry |
| Cost per nurse replacement | $40,000 - $64,000 | NurseRegistry |
| Total annual US cost of nurse turnover | $6.5B | Industry estimates |
| Impact of turnover: patient falls | +7% increase | Research |
| Impact of turnover: medication errors | +12% increase | Research |
| Impact of turnover: patient satisfaction | -15% decline | Research |
| Home health nurse satisfaction | Lowest of all nursing specialties | PMC research |
| Top driver of dissatisfaction | Administrative burden / documentation | Multiple sources |

### ROI Model for Ratchet

**Per-agency value proposition (mid-size agency, 200 nurses)**:

| Line Item | Calculation | Annual Value |
|-----------|-------------|--------------|
| Documentation time saved | 200 nurses x 30 min/day x 250 days x $40/hr | **$1,000,000** |
| Reduced turnover (5% improvement) | 10 fewer nurses leaving x $50,000 replacement cost | **$500,000** |
| Reduced after-hours overtime | 200 nurses x 3 hrs/week x 50 weeks x $20 OT premium | **$600,000** |
| Improved OASIS accuracy (fewer claim denials) | Estimated 2% improvement on $20M annual billing | **$400,000** |
| **Total annual value per agency** | | **$2,500,000** |
| **Ratchet annual cost** (200 nurses x $10/mo) | | **$24,000** |
| **ROI** | | **~100:1** |

---

## Key Takeaways for Go-to-Market

### 1. The HCHB Gap is Real and Urgent
HCHB controls 43.8% of home health but has no ambient AI documentation product. WellSky launched Scribe in Oct 2025. HCHB agencies are falling behind. This creates urgency for HCHB to partner or for agencies to adopt third-party solutions.

### 2. Two Go-to-Market Paths

**Path A: HCHB Partnership** (bigger, slower, higher ceiling)
- Approach HCHB as a technology partner for their ecosystem
- Leverage their partner program and 300,000+ user base
- Risk: HCHB may build their own or choose a different partner
- Upside: Instant distribution to 43.8% of the market

**Path B: Direct to Agencies** (faster, scrappier, prove-then-partner)
- Sell directly to mid-size HCHB agencies (Tier 2 targets)
- Build case studies and usage data
- Then approach HCHB with proven traction
- Risk: Integration friction without HCHB cooperation
- Upside: Faster to revenue, proves product-market fit

### 3. Competitive Window is 12-18 Months
WellSky Scribe launched Oct 2025. Narrable is active. nVoq is iterating. The ambient AI wave in home health is just starting. First-mover on HCHB/PointCare has significant advantage, but the window won't stay open forever.

### 4. The Buyer
- **At agencies**: Director of Clinical Operations, VP of Nursing, CIO/CTO, CFO (cost savings angle)
- **At HCHB**: VP of Product, VP of Partnerships/Business Development, CTO
- **Economic buyer**: CFO/COO (turnover cost, overtime, documentation efficiency)
- **Clinical champion**: Director of Nursing, Clinical Manager (burnout reduction, quality improvement)

### 5. Pricing Sweet Spot
Competitors range from $119-750/clinician/month but target physicians. Home health nurses are a different economic buyer (agencies pay, margins are thinner). Pricing at **$5-15/clinician/month** would be compelling vs. the $2,500,000/year value per mid-size agency.

---

## Sources

- [Mordor Intelligence - Home Healthcare Software Market](https://www.mordorintelligence.com/industry-reports/home-healthcare-software-market-industry)
- [Alora Health - Top 10 Home Health EMR Systems 2026](https://www.alorahealth.com/what-are-the-top-10-home-health-emr-systems-in-2026/)
- [TechTarget - Epic Among Leading Home Care EHR Vendors](https://www.techtarget.com/searchhealthit/news/366579268/Epic-Systems-Among-the-Leading-Home-Care-EHR-Vendors)
- [HCHB - PointCare Mobile Software](https://hchb.com/our-solutions/hchb-platform/mobile-pointcare/)
- [HCHB - 2024 Growth and Innovation](https://www.prnewswire.com/news-releases/homecare-homebase-wraps-2024-with-growth-product-innovation-and-industry-leadership-302354531.html)
- [HCHB - Partner Ecosystem](https://hchb.com/our-solutions/hchb-connect/hchb-partner-ecosystem/)
- [HCHB - Connect Interoperability](https://hchb.com/our-solutions/hchb-connect/)
- [Hearst Acquires HCHB (2013)](https://www.globenewswire.com/news-release/2013/12/02/1009733/0/en/Hearst-Corporation-Agrees-to-Acquire-an-85-Stake-in-Homecare-Homebase-LLC.html)
- [AccentCare - About](https://accentcare.com/about/)
- [Hospice News - AccentCare Unifies Brands](https://hospicenews.com/2022/01/03/accentcare-unifies-seven-brands-under-single-identity/)
- [Advent International Acquires AccentCare](https://hospicenews.com/2019/05/16/advent-international-to-acquire-post-acute-hospice-provider-accentcare/)
- [Definitive Healthcare - Top Home Health by Patient Volume](https://www.definitivehc.com/resources/healthcare-insights/top-home-health-corporations-total-patient-volume)
- [Definitive Healthcare - Top Home Health by Revenue](https://www.definitivehc.com/resources/healthcare-insights/home-health-agencies-net-patient-revenue)
- [WellSky - AI-Powered Ambient Listening](https://wellsky.com/wellsky-introduces-ai-powered-ambient-listening-and-transcription-capabilities-within-ehr-to-transform-the-home-health-visit/)
- [WellSky - 50% Documentation Time Reduction](https://wellsky.com/wellsky-ambient-listening-technology-helps-clinicians-reduce-documentation-time-by-up-to-50/)
- [Narrable Health](https://www.narrablehealth.com/)
- [Narrable - Guide to AI Ambient Scribes for Home Health](https://www.narrablehealth.com/resources/a-guide-to-ai-ambient-scribes-for-home-health-2025-edition)
- [nVoq - Speech Recognition for Home Health](https://www.nvoq.com/)
- [OrbDoc - Ambient Scribing for Home Health](https://orbdoc.com/blog/ambient-scribing-home-health)
- [OrbDoc - AI Medical Scribe Comparison](https://orbdoc.com/compare/ai-medical-scribe-comparison-2025)
- [Suki - $70M Funding](https://www.healthcaredive.com/news/suki-70-million-Series-D-funding/729573/)
- [Abridge - Enterprise Contracts](https://www.techtarget.com/searchhealthit/news/366614644/EHR-integration-drives-ambient-speech-purchasing-decisions)
- [Menlo Ventures - State of AI in Healthcare 2025](https://menlovc.com/perspective/2025-the-state-of-ai-in-healthcare/)
- [Grand View Research - US Home Healthcare Market](https://www.grandviewresearch.com/industry-analysis/us-home-healthcare-market-report)
- [Boost Home Health - 52 Statistics](https://boosthomehealth.com/home-health-statistics/)
- [Market.us - Home Healthcare Statistics](https://media.market.us/home-healthcare-statistics/)
- [CMS - Home Health Agencies](https://www.cms.gov/medicare/health-safety-standards/certification-compliance/home-health-agencies)
- [Home Health Care News - Medicare Agency Count Falling](https://homehealthcarenews.com/2023/07/with-access-to-care-in-question-number-of-medicare-certified-home-health-agencies-continues-to-fall/)
- [JAMIA - Documentation Burden in Nursing](https://academic.oup.com/jamia/article/28/5/998/6090156)
- [PMC - Documentation Burden and Burnout](https://pmc.ncbi.nlm.nih.gov/articles/PMC9581587/)
- [Timeero - Home Health Nurse Turnover](https://timeero.com/post/understanding-home-health-nurse-turnover-rates)
- [NurseRegistry - Cost of Nurse Turnover](https://www.nurseregistry.com/blog/cost-of-nurse-turnover/)
- [AACN - Nursing Documentation Burden](https://www.aacn.org/blog/nursing-documentation-burden-a-critical-problem-to-solve)
- [Axxess - Wikipedia](https://en.wikipedia.org/wiki/Axxess_Technology_Solutions)
- [SOLTECH - Aveanna Healthcare EMR Integration](https://soltech.net/software-case-studies/integration-healthcare-ehr-system/)
- [Samsung x HCHB Partnership](https://news.samsung.com/us/homecare-homebase-and-samsung-redefine-patient-care-for-home-health-and-hospice-markets-with-streamlined-enterprise-solutions/)
- [6sense - MatrixCare Market Share](https://6sense.com/tech/electronic-health-records-ehr/matrixcare-home-health-and-hospice-market-share)
