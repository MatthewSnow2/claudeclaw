# Ratchet / Beth Go-to-Market: Healthcare Compliance Review

**Prepared**: 2026-02-26
**Prepared for**: M2AI (Matthew Snow)
**Subject**: Regulatory, compliance, and legal requirements for Ratchet -- an AI-powered MCP tool for home health nurse documentation
**Status**: Pre-revenue, pre-PHI, mock data only

---

## Executive Summary

Ratchet faces a significant compliance burden before it can touch real patient data or be sold to healthcare organizations. The core challenge: M2AI is a one-person consultancy with no existing compliance certifications, selling into one of the most regulated industries in the U.S.

The good news: Ratchet is a documentation *assistant*, not a diagnostic tool. This keeps it out of FDA medical device territory. The bad news: it still handles PHI, requires HIPAA compliance across every layer of the stack, and healthcare buyers have non-negotiable security requirements that take months and real money to satisfy.

**Bottom line**: M2AI needs 3-6 months and $30K-$80K in compliance investment before signing any contract that involves real patient data. Some of this can run in parallel with sales conversations, but the BAAs, encryption, and audit logging cannot be hand-waved.

---

## 1. HIPAA Compliance Checklist

### 1.1 Business Associate Agreement (BAA)

Ratchet, operated by M2AI, would be classified as a **Business Associate (BA)** under HIPAA. M2AI creates, receives, maintains, or transmits PHI on behalf of a Covered Entity (the home health agency).

**What M2AI needs:**

| Item | Details |
|------|---------|
| BAA with the customer | The home health agency (e.g., AccentCare) is the Covered Entity. M2AI signs a BAA with them, committing to HIPAA safeguards. This is non-negotiable -- no agency will use Ratchet without one. |
| BAA with Anthropic (Claude) | Anthropic offers BAAs for first-party API customers with Zero Data Retention (ZDR) agreements. Requires contacting Anthropic sales directly, demonstrating a clear healthcare use case, and getting approved. BAAs signed after Dec 2, 2025 can cover both API and Enterprise plan usage. |
| BAA with Supabase | Supabase offers BAAs on the Team plan ($599/mo) with the HIPAA add-on ($350/mo). Total minimum: $949/month. The BAA triggers additional security controls and ongoing compliance audits. |
| BAA with any subcontractor | Any other service touching PHI (hosting, analytics, monitoring) requires its own BAA. Netlify does NOT offer BAAs -- the demo dashboard cannot host real PHI. |

**Who signs what:**
- M2AI signs a BAA *with* each healthcare customer (M2AI = Business Associate)
- M2AI signs BAAs *from* its subprocessors: Anthropic, Supabase, and any other vendor touching PHI
- This creates a chain: Covered Entity -> M2AI (BA) -> Anthropic/Supabase (Subcontractor BAs)

### 1.2 Protected Health Information (PHI) in Ratchet

Everything Ratchet handles in production qualifies as PHI:

| Data Element | PHI? | Notes |
|-------------|------|-------|
| Patient name | Yes | Direct identifier |
| Date of visit | Yes | Date element linked to individual |
| Address / location of visit | Yes | Geographic data smaller than state |
| Vitals (BP, temp, O2 sat, etc.) | Yes | Clinical data linked to individual |
| Medications, dosages | Yes | Treatment information |
| Diagnoses, conditions | Yes | Clinical data |
| SOAP notes (full text) | Yes | Clinical narrative |
| Voice recordings (if stored) | Yes | Contains all of the above in audio form |
| Nurse identifier + patient link | Yes | Links workforce member to patient |
| Insurance/billing codes | Yes | If generated or referenced |

**Critical point**: Even the *transcription* of a nurse's voice dictation is PHI the moment it references an identifiable patient. The voice audio itself is PHI if stored or transmitted.

### 1.3 Data Encryption Requirements

**HIPAA Security Rule (45 CFR 164.312):**

| Requirement | Standard | Notes |
|-------------|----------|-------|
| Data in transit | TLS 1.2+ (AES-256) | All API calls, data transfers. HTTPS everywhere. No exceptions. |
| Data at rest | AES-256 encryption | Database encryption, file storage, backups. Supabase HIPAA add-on enables this. |
| Voice data (if stored) | AES-256 at rest, TLS in transit | Voice recordings are PHI. Must be encrypted or not stored at all. |
| Encryption key management | Documented key rotation policy | Who holds keys, how often rotated, access controls on key material. |
| Backup encryption | Same as primary data | Backups must be encrypted to the same standard. |

**Note**: HIPAA technically lists encryption as "addressable" not "required" -- but in practice, any auditor or buyer will treat unencrypted PHI as a compliance failure. There is no defensible reason not to encrypt.

### 1.4 Access Controls

**Required under HIPAA Security Rule:**

| Control | Requirement |
|---------|-------------|
| Unique user identification | Every user has a unique ID. No shared accounts. |
| Emergency access procedure | Documented process for accessing PHI in emergencies. |
| Automatic logoff | Sessions timeout after inactivity. |
| Authentication | Strong passwords + MFA for any system accessing PHI. |
| Role-based access | Nurses see their patients. Admins see audit logs. Principle of least privilege. |
| Audit logging | Every access to PHI must be logged: who, what, when, from where. Logs must be tamper-evident and retained for 6 years. |
| Device management | If Ratchet runs on nurse tablets/phones, those devices need encryption, remote wipe capability, and PIN/biometric lock. |

**Audit logging is the sleeper requirement.** Healthcare buyers will ask for it in every security questionnaire. Ratchet needs to log every SOAP note creation, edit, view, and export with timestamps and user IDs from day one.

### 1.5 Breach Notification Requirements

If PHI is compromised, HIPAA's Breach Notification Rule (45 CFR 164.400-414) requires:

| Action | Timeline | Details |
|--------|----------|---------|
| Risk assessment | Immediately upon discovery | Determine if breach occurred (nature, extent, mitigation, likelihood of re-identification) |
| Notify Covered Entity | Without unreasonable delay, max 60 days | As a BA, M2AI must notify the healthcare customer. The BAA will specify the exact timeline (often 24-72 hours). |
| Customer notifies individuals | Within 60 days of discovery | The Covered Entity (not M2AI) notifies affected patients. |
| HHS notification | 60 days (500+ records) or annual (under 500) | Breaches of 500+ records require immediate HHS notification and media notification in the affected state. |
| Documentation | Retain for 6 years | All breach-related documentation, investigation notes, notifications sent. |

**Penalties:**
- $137 to $68,928 per violation, up to $2.13M per violation category per year
- Criminal penalties possible for willful neglect
- State attorneys general can bring additional actions ($1K-$10K per individual affected)
- Presense Health paid $475,000 solely for exceeding the 60-day notification window

**M2AI needs**: A written Incident Response Plan (IRP) before handling any PHI. This is a standard security questionnaire item.

### 1.6 HIPAA Training Requirements

Even as a one-person company, M2AI must:

| Requirement | Details |
|-------------|---------|
| Complete HIPAA training | Security Rule explicitly requires training for all workforce members, including management. |
| Document completion | Maintain records of training completion with dates. |
| Refresh annually | Training must be repeated when policies change or at regular intervals. |
| Cover all three rules | Privacy Rule, Security Rule, and Breach Notification Rule. |
| Cost | Online HIPAA training courses: $25-$200 per person. |

**Practical note**: For a sole proprietor, this is straightforward but must be documented. An auditor or customer security questionnaire will ask for proof of HIPAA training.

### 1.7 Supabase HIPAA Status

**Verdict: Acceptable with the right plan and configuration.**

- Supabase is HIPAA-compliant and will sign a BAA.
- Requires: Team plan ($599/mo) + HIPAA add-on ($350/mo) = **$949/month minimum**.
- HIPAA add-on enables: additional security controls, continuous compliance monitoring, security warnings for non-compliant settings.
- Supabase is SOC 2 Type II certified, and HIPAA controls are audited during the same audit period.
- **Shared Responsibility Model**: Supabase handles infrastructure-level compliance. M2AI is responsible for application-level controls (access management, audit logging, data handling within the app).

**Current concern**: Ratchet currently uses Supabase on what appears to be a standard plan with no BAA. This is fine for mock data but must be upgraded before any real PHI enters the system.

### 1.8 Anthropic (Claude) HIPAA Status

**Verdict: Available but requires enterprise engagement.**

- Anthropic offers BAAs for first-party API customers.
- Requires **Zero Data Retention (ZDR)** agreement -- Anthropic does not store inputs or outputs.
- Must be negotiated directly with Anthropic sales team. Not available self-serve.
- BAAs signed after December 2, 2025 can cover both API usage and Enterprise plan.
- Claude Desktop (the current Ratchet interface) is **NOT covered** by BAAs. Only the first-party API is eligible.
- **Claude Desktop cannot be used with real PHI.** Ratchet must use the API directly.

**Action required**: Contact Anthropic sales, explain the Ratchet use case, negotiate ZDR + BAA. Timeline: weeks to months depending on Anthropic's review process.

---

## 2. SOC 2 Assessment

### 2.1 Is SOC 2 Required?

**Not legally required, but practically expected.** SOC 2 is not a regulatory mandate. However:

- Most enterprise healthcare buyers include SOC 2 (or equivalent) in their vendor security questionnaires
- AccentCare holds HITRUST certification and will likely expect comparable diligence from vendors
- Without SOC 2, M2AI will face objections in procurement and InfoSec review cycles
- SOC 2 is the most commonly requested third-party attestation for SaaS/cloud vendors

### 2.2 Type 1 vs. Type 2

| Aspect | SOC 2 Type 1 | SOC 2 Type 2 |
|--------|--------------|--------------|
| What it proves | Controls are designed correctly at a point in time | Controls operated effectively over 3-12 months |
| Timeline | 2-4 months (prep + audit) | 6-15 months (prep + observation period + audit) |
| Cost (small company) | $20,000 - $40,000 | $35,000 - $80,000 |
| Buyer acceptance | Gets you in the door for initial conversations | Required for ongoing enterprise relationships |
| Recommendation | Start here | Target within 12 months of first customer |

**Recommended path for M2AI:**
1. Start SOC 2 Type 1 immediately (can run in parallel with sales)
2. Begin the observation period for Type 2 as soon as Type 1 is complete
3. Use a compliance automation platform (Vanta, Drata, Secureframe) to reduce manual effort -- $5K-$15K/year but saves significant time for a solo operator

### 2.3 Cost Breakdown (Realistic for M2AI)

| Item | Estimated Cost | Notes |
|------|---------------|-------|
| Compliance automation platform | $5,000 - $15,000/year | Vanta, Drata, or Secureframe. Handles evidence collection, policy templates, continuous monitoring. |
| SOC 2 Type 1 audit (CPA firm) | $10,000 - $25,000 | Smaller firms charge less. |
| Policy/procedure development | $0 - $5,000 | Templates from automation platform, or hire a consultant. |
| Remediation costs | $2,000 - $10,000 | Fixing gaps found during readiness assessment. |
| **Total for Type 1** | **$20,000 - $50,000** | |
| SOC 2 Type 2 audit (subsequent) | $15,000 - $35,000 | After 3-12 month observation period. |

**Biggest cost for a one-person company**: Time. SOC 2 prep requires a dedicated project owner at 50-100% capacity for 4-6 months. For M2AI, this is Matthew. This is real opportunity cost.

### 2.4 Alternatives: What Home Health Agencies Actually Ask For

| Framework | Relevance | Cost | Timeline | Notes |
|-----------|-----------|------|----------|-------|
| **SOC 2 Type 1** | High | $20K-$50K | 3-4 months | Most commonly requested. Good starting point. |
| **SOC 2 Type 2** | High | $35K-$80K | 9-15 months | Required for ongoing enterprise contracts. |
| **HITRUST e1** | Very High | $40K-$80K | 4-6 months | Healthcare-specific. AccentCare has HITRUST -- they may prefer HITRUST-certified vendors. |
| **HITRUST i1** | Very High | $80K-$120K | 6-9 months | Mid-tier HITRUST. 5x more controls than SOC 2. |
| **HITRUST r2** | Highest | $150K-$300K+ | 12-18 months | Gold standard. AccentCare holds this. Overkill for M2AI's current stage. |
| **ISO 27001** | Moderate | $30K-$60K | 6-12 months | International standard. Less common ask in U.S. home health. |

**Recommendation**: Start with SOC 2 Type 1. If AccentCare or similar buyers specifically require HITRUST, pivot to HITRUST e1 (the entry-level tier). Many compliance platforms support both frameworks simultaneously.

**Key insight**: AccentCare achieved HITRUST r2 certification for their HCHB instances. They will absolutely scrutinize vendor security posture. M2AI should expect a thorough security questionnaire during procurement.

---

## 3. AI-Specific Regulations

### 3.1 FDA Medical Device Classification

**Does Ratchet qualify as a medical device?**

**Most likely: No.** Here's the analysis:

The FDA regulates Software as a Medical Device (SaMD) when software is intended to diagnose, treat, cure, mitigate, or prevent disease. Ratchet's function is **documentation assistance** -- it converts voice/natural language input into structured SOAP notes. It does not:
- Make diagnostic decisions
- Recommend treatments
- Analyze clinical data to produce clinical insights
- Directly influence clinical decision-making

**However, watch the boundaries carefully:**

| Feature | FDA Risk Level |
|---------|---------------|
| Transcribing nurse dictation into SOAP format | Not a medical device -- administrative/documentation tool |
| Auto-populating vitals from voice input | Gray area -- if it *interprets* or *validates* vitals, could cross the line |
| Suggesting care plan elements | Higher risk -- if Ratchet recommends clinical actions, it starts looking like Clinical Decision Support (CDS) |
| Flagging abnormal vitals | Definitely CDS -- would require FDA oversight |
| Generating OASIS assessment items | Very high risk -- OASIS drives reimbursement and care planning |

**Recommendation**: Keep Ratchet firmly in the "documentation assistant" lane. The nurse dictates, Ratchet structures. Ratchet does not interpret, recommend, or flag. Any feature that crosses into clinical decision support should be evaluated against FDA's September 2022 CDS guidance criteria before implementation.

The FDA's January 2025 Draft Guidance on AI-Enabled Device Software Functions would apply if Ratchet ever crosses into SaMD territory. That guidance requires: model descriptions, data lineage, performance claims, bias analysis, human-AI workflow documentation, and post-market monitoring plans.

### 3.2 CMS Documentation Requirements for Home Health

CMS requires specific documentation for home health services to support reimbursement under Medicare:

| Requirement | Standard | Can AI Help? |
|-------------|----------|--------------|
| OASIS assessments | OASIS-E1 (effective Jan 2025), OASIS-E2 (April 2026) | Yes, but nurse must review and sign. AI cannot independently complete OASIS. |
| SOAP notes per visit | Must support medical necessity, document interventions, reflect patient response | Yes -- this is Ratchet's core use case. Notes must be clinician-reviewed and signed. |
| Plan of Care (485) | Physician-ordered, updated every 60 days | AI can draft, but physician must sign. |
| Timely documentation | Notes should be completed same-day or within agency policy (typically 24-48 hours) | AI reduces documentation time significantly -- this is a selling point. |
| All-payer OASIS | Mandatory collection began July 1, 2025 | Increases documentation burden -- another selling point for Ratchet. |

**Critical CMS compliance point**: AI-generated documentation is acceptable IF the clinician reviews, edits as needed, and attests to its accuracy by signing. The clinician's signature means they take responsibility for the content. Ratchet must make this review-and-sign workflow explicit and unavoidable.

Industry precedent: Tools like Apricot already offer AI-drafted OASIS forms using patient referral documents. The model is consistent -- AI drafts, clinician reviews and owns the final product. CMS has not prohibited AI-assisted documentation.

### 3.3 State-Specific AI Healthcare Regulations

As of early 2026, 47 states have introduced healthcare AI bills. Key laws affecting Ratchet:

| State | Law | Requirement | Effective |
|-------|-----|-------------|-----------|
| **California** | AB 3030 | Disclosure to patients that AI generated or assisted in clinical communications. Clear instructions for contacting a licensed provider. | 2025 |
| **Texas** | SB 1188 / HB 1709 | Written disclosure to patients before or on date of service that AI is being used. Practitioners must personally review all AI-generated content before clinical decisions. | Jan 1, 2026 |
| **Illinois** | HB 1806 | AI cannot make independent therapeutic decisions. Licensed professional must review and approve all AI-generated treatment plans and clinical recommendations. | Aug 1, 2025 |
| **Colorado** | AI Act | Risk management policies, AI impact assessments, and anti-discrimination measures for high-risk AI in healthcare. | 2026 |
| **Pennsylvania** | Proposed | Disclaimers when AI generates clinical communications; disclosure of AI in clinical decision-making. | Pending |

**Impact on Ratchet**: Every state where Ratchet operates may require patient notification that AI is involved in documentation. The product UX should include a standard disclosure mechanism, and documentation should carry an indicator that AI assisted in generation.

**Recommendation**: Build a state-regulation tracking process. The landscape is changing rapidly. Ratchet's terms of service and product documentation should include boilerplate about AI disclosure requirements, and the product should support configurable disclosure notices per state.

### 3.4 Liability for Incorrect AI-Generated Notes

**Who is liable if Ratchet generates a note with incorrect information (wrong medication, wrong vital sign)?**

The legal landscape is evolving, but the current framework is clear:

| Party | Liability Exposure | Rationale |
|-------|-------------------|-----------|
| **The signing clinician** | Primary | The nurse who reviews and signs the note attests to its accuracy. This is no different from a human scribe error -- the signing clinician owns the record. Courts and licensing boards hold the signer accountable. |
| **M2AI (Ratchet)** | Secondary, growing | Product liability theories (defective product, failure to warn). If Ratchet has a systematic error pattern and M2AI knew or should have known, liability attaches. Negligence claims if the system was not adequately tested or if known failure modes were not disclosed. |
| **The healthcare agency** | Vicarious | Responsible for selecting and overseeing tools used by their clinicians. If the agency failed to vet Ratchet or didn't require clinician review, they share liability. |

**Key legal precedents and trends:**
- Clinicians have been sued for copy-pasting past notes without updating -- the same theory applies to blindly signing AI-generated notes.
- The standard of care is evolving: if AI documentation tools become pervasive, *not* using them (or not reviewing their output) could itself become a liability.
- Courts have not yet established extensive precedent for AI-assisted malpractice. The question of product liability vs. malpractice doctrine remains open.

**M2AI's mitigation strategy:**
1. **Mandatory clinician review**: The product must require review and signature before any note is finalized. No auto-submission.
2. **Clear terms of service**: Ratchet is a documentation *assistant*. The clinician is responsible for reviewing and approving all content.
3. **Warnings and flagging**: When confidence is low or input is ambiguous, Ratchet should flag sections for extra review.
4. **Professional liability insurance**: M2AI should carry Errors & Omissions (E&O) insurance and possibly product liability coverage. Estimated $2K-$10K/year for a small SaaS.
5. **Documentation best practices guidance**: Train users to always review AI output, especially medications, dosages, and vital signs.

### 3.5 AI Hallucination Risk

This is the #1 clinical safety concern. Research on ambient AI scribes shows:

| Metric | Finding |
|--------|---------|
| Overall error rate | ~1-3% in modern LLM-based scribes |
| Types of errors | Hallucinations (fabricated content), critical omissions, misattribution, contextual misinterpretation |
| Clinical significance | Even 1-3% error rates are significant in healthcare -- a single wrong medication or dosage can cause patient harm |

**Industry best practices for mitigation:**

1. **Mandatory human review before finalization** -- industry standard; no exceptions
2. **Confidence indicators** -- flag low-confidence sections (uncertain transcription, ambiguous input)
3. **Structured output validation** -- validate vitals against physiological ranges (e.g., BP of 300/200 is obviously wrong)
4. **Medication cross-referencing** -- check generated medication names against drug databases
5. **Audit trails** -- log the original input alongside the AI-generated output for retrospective review
6. **No auto-population into EMR** -- require explicit clinician action to transfer notes to the EMR
7. **Regular accuracy monitoring** -- track error rates in production and publish them to customers
8. **Patient consent for AI documentation** -- notify patients that AI assists in documentation (also a legal requirement in many states)

---

## 4. EMR Integration Requirements

### 4.1 What EMR Vendors Typically Require

Third-party vendors seeking to integrate with EMR systems generally face:

| Requirement | Details |
|-------------|---------|
| Security review | Comprehensive security questionnaire (SIG, CAIQ, or custom). Often 200-400 questions. |
| Compliance certifications | SOC 2, HITRUST, or equivalent. Some EMRs require specific certifications. |
| BAA execution | Standard requirement for any vendor touching PHI. |
| Penetration testing | Annual third-party pentest report. |
| Insurance | Professional liability (E&O), cyber liability, general liability. Minimum coverage amounts specified. |
| Technical review | API design review, data flow documentation, architecture assessment. |
| Pilot/sandbox period | Testing in non-production environment before production access. |
| Ongoing monitoring | Regular security assessments, compliance attestation renewal. |

### 4.2 HCHB Integration Landscape

**Homecare Homebase (HCHB):**

- HCHB offers **HCHB Connect** -- their interoperability ecosystem for third-party integrations.
- **HCHB Partner Ecosystem** -- a select group of preferred third-party vendors. Getting into this ecosystem requires HCHB's approval.
- **Custom Integration Services** -- HCHB builds custom integrations for home health, hospice, and personal care providers.
- No publicly documented developer portal with self-serve API access (unlike PointClickCare).
- Integration is reportedly difficult. Third-party platforms like AIR Platform exist specifically to facilitate HCHB integrations.
- HCHB holds HIPAA and HITRUST certifications. They will expect the same from integration partners.

**PointCare (HCHB's mobile app):**

- PointCare is HCHB's mobile clinical visit application (package: com.hchb.pc.ui). It provides field clinicians with access to clinical information for patient visits.
- PointCare is not a separate EMR -- it's the mobile interface to HCHB.
- Direct integration with PointCare would require HCHB's cooperation and approval.

**Practical path for Ratchet:**
1. **Phase 1 (Near-term)**: Ratchet generates SOAP notes that nurses manually copy/paste or transfer into PointCare/HCHB. No direct integration needed. Lower compliance bar.
2. **Phase 2 (Medium-term)**: Explore HCHB Connect partnership. Requires SOC 2 or HITRUST, BAA, security review, and likely a champion inside AccentCare or HCHB.
3. **Phase 3 (Long-term)**: Direct API integration via HCHB Connect or custom integration. Full compliance stack required.

### 4.3 PointClickCare (for context)

PointClickCare (distinct from PointCare) has a published **Developer Program** at developer.pointclickcare.com and a **FHIR API** at fhir.pointclickcare.com. This is much more accessible than HCHB's model. If Ratchet expands beyond HCHB-based agencies, PointClickCare integration would be more straightforward.

### 4.4 Interoperability Standards

| Standard | Relevance to Ratchet | Required? |
|----------|----------------------|-----------|
| **FHIR (R4)** | Modern REST API standard for health data exchange. Increasingly mandated by ONC. | Not immediately, but building FHIR-compatible data models now saves pain later. |
| **HL7 v2** | Legacy messaging standard. Still dominant in hospital workflows. | Unlikely needed for home health documentation. |
| **CDA (C-CDA)** | Document-based exchange format. Used in care transitions. | May be required if Ratchet needs to generate exportable clinical documents. |
| **USCDI** | United States Core Data for Interoperability. Defines minimum data elements for exchange. | Relevant when building FHIR resources. Good to align Ratchet's data model with USCDI. |
| **CommonWell / Carequality** | Health information exchange networks. | Not needed for initial Ratchet use case (within-agency documentation). |

**Recommendation**: Build Ratchet's internal data model to align with FHIR resource types (Patient, Encounter, Observation, Condition, MedicationStatement, DocumentReference) even if you're not exposing FHIR APIs initially. This makes future integration dramatically easier.

---

## 5. Data Architecture Concerns

### 5.1 Supabase for PHI Storage

**Verdict: Acceptable with proper configuration. Not free.**

| Aspect | Status |
|--------|--------|
| HIPAA compliance | Yes, with Team plan + HIPAA add-on |
| BAA available | Yes |
| Encryption at rest | Yes (AES-256), enabled by HIPAA add-on |
| Encryption in transit | Yes (TLS) |
| SOC 2 Type II | Yes |
| Annual HIPAA audits | Yes (audited alongside SOC 2) |
| Row Level Security (RLS) | Available -- M2AI must implement per-patient access controls |
| Audit logging | Application-level logging is M2AI's responsibility |
| Cost | $949/month minimum (Team $599 + HIPAA $350) |

**What M2AI must do (not covered by Supabase):**
- Implement Row Level Security policies to enforce per-user/per-patient access
- Build application-level audit logging (Supabase provides database logs, but not application-level access logs)
- Configure proper backup and retention policies
- Ensure no PHI leaks into Supabase's free-tier features (e.g., Supabase Dashboard access, Realtime subscriptions without auth)

### 5.2 Anthropic API + Claude for Clinical Data

**Verdict: Possible but requires specific arrangements.**

| Concern | Status |
|---------|--------|
| BAA available | Yes, for API customers with ZDR agreements |
| Zero Data Retention | Available -- Anthropic does not store inputs/outputs |
| Data training | With ZDR, data is not used for model training |
| Claude Desktop | **NOT covered.** Cannot be used with real PHI. |
| API access | Must use first-party API (api.anthropic.com) directly |
| AWS Bedrock alternative | Claude is available via AWS Bedrock, which has its own BAA and HIPAA compliance. May be easier path. |

**Architecture implication**: Ratchet cannot use Claude Desktop as the production interface for PHI. The current architecture (MCP tool via Claude Desktop) works for demos with mock data but must be redesigned for production. Options:

1. **Direct API integration**: Ratchet's backend calls the Anthropic API directly. Frontend is a custom web/mobile app. Most control, most work.
2. **AWS Bedrock**: Use Claude via Bedrock. AWS handles HIPAA compliance at the infrastructure level. Adds AWS cost but simplifies compliance.
3. **Hybrid**: Claude Desktop for demo/mock mode, API for production. Clear separation of environments.

### 5.3 Data Geography

| Concern | Details |
|---------|---------|
| Supabase regions | Choose US regions. HIPAA data should not leave the United States without explicit contractual authorization. |
| Anthropic API | Processed in the US. With ZDR, data is not persisted. |
| AWS Bedrock (if used) | Specify us-east-1 or us-west-2. |
| Netlify (demo dashboard) | Netlify does not offer BAAs. Cannot host any PHI-adjacent features. Fine for marketing/demo sites with synthetic data only. |
| Voice data routing | If voice transcription happens before Claude processing, the transcription service also needs a BAA and US data residency. |

**Note**: Some healthcare contracts include data residency clauses requiring data to remain within the continental US. Check each customer's requirements.

### 5.4 Data Retention Policies

CMS and state regulations have specific retention requirements:

| Data Type | Minimum Retention | Notes |
|-----------|-------------------|-------|
| Clinical documentation (SOAP notes) | 5-10 years (varies by state) | Many states require 7 years. Some require 10. Pediatric records may need to be kept until the patient turns 21 + statute of limitations. |
| OASIS assessments | 5 years (CMS requirement) | May be longer under state law. |
| Audit logs | 6 years (HIPAA Security Rule) | Logs of who accessed what PHI, when. |
| BAA documentation | 6 years from termination | Required by HIPAA. |
| Breach investigation records | 6 years | Required by HIPAA. |

**M2AI's responsibility**: Even if the healthcare agency retains records in their EMR, if M2AI stores any PHI (even temporarily), M2AI needs a documented retention and destruction policy. This includes:
- How long data is stored in Supabase
- When and how data is purged
- How deletion is verified
- Process for honoring data deletion requests from customers

### 5.5 Right to Deletion / Data Lifecycle

HIPAA does not grant patients a general right to delete their medical records (unlike GDPR). However:

- Patients can request amendments to their records
- Healthcare agencies may have contractual obligations to delete vendor-held data upon contract termination
- M2AI's BAA should include clear data return/destruction clauses
- California (CCPA/CPRA) provides deletion rights for non-PHI data, but PHI handled under HIPAA is generally exempt from CCPA

**Key contract clause**: When a customer terminates, M2AI must return or destroy all PHI within a specified period (typically 30-60 days) and certify destruction in writing.

---

## 6. Risk Assessment

### Top 5 Compliance Risks (Ranked by Severity x Likelihood)

#### Risk #1: PHI Exposure Through Claude Desktop (CRITICAL)

| Dimension | Assessment |
|-----------|-----------|
| Severity | Critical |
| Likelihood | High (current architecture uses Claude Desktop) |
| Description | Claude Desktop is not covered by Anthropic's BAA. Sending real patient data through Claude Desktop is a HIPAA violation. Any demo with real PHI in the current architecture is non-compliant. |
| Mitigation | Redesign production architecture to use Claude API directly (with ZDR + BAA) or via AWS Bedrock. Maintain strict separation: Claude Desktop = mock data only. |
| Cost to fix | $5K-$15K (architecture redesign) + Anthropic enterprise engagement |
| Timeline | 4-8 weeks for architecture work; Anthropic BAA negotiation may take longer |

#### Risk #2: No BAA Chain in Place (CRITICAL)

| Dimension | Assessment |
|-----------|-----------|
| Severity | Critical |
| Likelihood | Certain (no BAAs exist today) |
| Description | M2AI has no BAAs with Anthropic, Supabase, or potential customers. Without BAAs, any PHI handling is a HIPAA violation. Healthcare organizations cannot legally share PHI with M2AI without a signed BAA. |
| Mitigation | Execute BAAs with Anthropic (API + ZDR) and Supabase (Team + HIPAA add-on) before any PHI touches the system. Prepare a standard BAA template for customer agreements. |
| Cost to fix | Legal review of BAAs: $2K-$5K. Supabase upgrade: $949/month. Anthropic: custom pricing TBD. |
| Timeline | 4-8 weeks (Supabase is fast; Anthropic requires sales engagement) |

#### Risk #3: AI Hallucination Causing Clinical Harm (HIGH)

| Dimension | Assessment |
|-----------|-----------|
| Severity | High (patient safety + legal liability) |
| Likelihood | Moderate (1-3% error rate is documented in ambient AI scribes) |
| Description | Ratchet generates a SOAP note with fabricated or incorrect clinical information (wrong medication, wrong dosage, hallucinated vital sign). If the nurse signs without catching the error, it becomes part of the medical record and could affect patient care. |
| Mitigation | Mandatory review workflow (no auto-finalization). Structured validation (range checks on vitals, medication name verification). Confidence scoring with visual flags. Clear terms of service placing review responsibility on the clinician. E&O insurance. |
| Cost to fix | $5K-$20K (validation logic, UX for review workflow) + $2K-$10K/year (E&O insurance) |
| Timeline | 4-6 weeks for core safety features |

#### Risk #4: No Audit Logging or Access Controls (HIGH)

| Dimension | Assessment |
|-----------|-----------|
| Severity | High |
| Likelihood | High (not yet implemented) |
| Description | HIPAA requires comprehensive audit trails for all PHI access. Healthcare buyers will require this in security questionnaires. Without it, M2AI fails the most basic vendor security review. |
| Mitigation | Implement audit logging from the start: every SOAP note creation, edit, view, and export logged with user ID, timestamp, IP address, and action type. Implement RBAC. Add session management with auto-logoff. |
| Cost to fix | $3K-$8K (engineering time) |
| Timeline | 2-4 weeks |

#### Risk #5: No Compliance Certifications for Enterprise Sales (MEDIUM-HIGH)

| Dimension | Assessment |
|-----------|-----------|
| Severity | Medium (deal-breaker for larger agencies, less critical for small ones) |
| Likelihood | High (AccentCare has HITRUST -- they will expect vendor diligence) |
| Description | Without SOC 2 or HITRUST, M2AI will struggle to pass procurement security reviews at established home health agencies. This doesn't prevent demos or pilots with mock data, but blocks production contracts. |
| Mitigation | Begin SOC 2 Type 1 process immediately. Use compliance automation platform. Consider HITRUST e1 if AccentCare specifically requests it. |
| Cost to fix | $20K-$50K (SOC 2 Type 1) |
| Timeline | 3-6 months |

---

## 7. "Table Stakes" List

### Non-Negotiable: Must Be Done BEFORE Approaching Healthcare Orgs with Real PHI

These are absolute requirements. No healthcare organization's legal or compliance team will approve a vendor relationship without them.

| # | Requirement | Est. Cost | Est. Timeline | Notes |
|---|-------------|-----------|---------------|-------|
| 1 | **Signed BAA with Anthropic** (API + ZDR) | Custom (sales engagement) | 4-12 weeks | Cannot send PHI to Claude without this. Blocks everything. |
| 2 | **Signed BAA with Supabase** (Team + HIPAA add-on) | $949/month ongoing | 1-2 weeks | Supabase process is straightforward. Upgrade plan and enable add-on. |
| 3 | **Production architecture off Claude Desktop** | $5K-$15K eng time | 4-8 weeks | Use Claude API directly or via AWS Bedrock. Claude Desktop is not HIPAA-eligible. |
| 4 | **Written HIPAA policies and procedures** | $2K-$5K (templates + legal review) | 2-4 weeks | Privacy Policy, Security Policy, Breach Notification Policy, Incident Response Plan, Risk Management Plan. |
| 5 | **Data encryption** (at rest + in transit) | Included in Supabase HIPAA | 1-2 weeks | Verify all data flows are TLS 1.2+. Supabase HIPAA add-on handles at-rest. |
| 6 | **Audit logging** | $3K-$8K eng time | 2-4 weeks | Log all PHI access with user, action, timestamp. 6-year retention. |
| 7 | **Access controls (RBAC + MFA)** | $2K-$5K eng time | 2-3 weeks | Unique user IDs, role-based access, MFA, session timeout. |
| 8 | **HIPAA training** (documented) | $25-$200 | 1 day | Complete online HIPAA training. Keep certificate. |
| 9 | **Standard BAA template for customers** | $2K-$5K (attorney review) | 1-2 weeks | Have a BAA ready to present to healthcare customers. They may provide their own, but be prepared. |
| 10 | **E&O / Professional Liability Insurance** | $2K-$10K/year | 1-2 weeks | Many enterprise customers require proof of insurance. |
| 11 | **Mandatory clinician review workflow** | $3K-$8K eng time | 2-4 weeks | No note can be finalized without explicit clinician review and signature. Non-negotiable for clinical safety. |
| 12 | **Incident Response Plan** | $1K-$3K | 1-2 weeks | Written plan for breach detection, containment, notification. Required by HIPAA. |
| 13 | **HIPAA Risk Assessment** | $3K-$10K (consultant or DIY) | 2-4 weeks | Required by HIPAA Security Rule. Must be documented and repeated annually. |

**Total estimated "table stakes" investment**: $25K-$70K + $949/month ongoing (Supabase) + insurance + Anthropic API costs

**Total timeline (parallel execution)**: 8-12 weeks

### Nice-to-Have Differentiators

These strengthen the sales pitch and accelerate procurement but are not absolute blockers for initial conversations:

| # | Item | Est. Cost | Est. Timeline | Impact |
|---|------|-----------|---------------|--------|
| 1 | SOC 2 Type 1 certification | $20K-$50K | 3-6 months | Opens doors with enterprise buyers. Can start process during early sales. |
| 2 | HITRUST e1 certification | $40K-$80K | 4-6 months | Preferred by healthcare-native buyers like AccentCare. |
| 3 | Third-party penetration test | $5K-$15K | 2-4 weeks | Many security questionnaires require this. Annual cadence. |
| 4 | FHIR-compatible data model | $5K-$10K eng time | 2-4 weeks | Future-proofs for EMR integration. |
| 5 | State regulation compliance engine | $3K-$8K eng time | 2-4 weeks | Configurable AI disclosure notices per state. |
| 6 | Accuracy monitoring dashboard | $5K-$10K eng time | 3-4 weeks | Track and publish AI accuracy rates. Builds trust. |
| 7 | Cyber liability insurance | $3K-$10K/year | 1-2 weeks | Beyond E&O -- covers breach response costs. |

### What Can Run in Parallel with Sales Conversations

| Activity | Can start before compliance is complete? |
|----------|------------------------------------------|
| Demo with synthetic/mock data | Yes -- no PHI, no HIPAA obligation |
| Discovery calls and needs assessment | Yes -- no data exchange needed |
| Security questionnaire (pre-fill) | Yes -- shows intent, surfaces specific requirements |
| SOC 2 prep (readiness assessment) | Yes -- show you're in process |
| BAA negotiation with customer | Yes -- can happen before cert is complete |
| Pilot with real PHI | **No** -- all table stakes must be complete first |
| Production deployment | **No** -- full compliance stack required |
| HCHB integration | **No** -- requires compliance certs + HCHB partner approval |

---

## Appendix A: Compliance Cost Summary

| Category | One-Time Cost | Recurring (Annual) |
|----------|--------------|-------------------|
| Legal (BAAs, policies, attorney) | $5K-$15K | $2K-$5K (annual review) |
| Supabase HIPAA | -- | $11,388/year ($949/mo) |
| Anthropic API (ZDR + BAA) | TBD (sales negotiation) | Usage-based |
| Engineering (security features) | $15K-$40K | $5K-$10K (maintenance) |
| SOC 2 Type 1 | $20K-$50K | -- |
| SOC 2 Type 2 (Year 2) | -- | $15K-$35K |
| Compliance automation platform | -- | $5K-$15K |
| Insurance (E&O + Cyber) | -- | $5K-$20K |
| HIPAA training | $25-$200 | $25-$200 |
| Penetration testing | $5K-$15K | $5K-$15K |
| HIPAA Risk Assessment | $3K-$10K | $3K-$10K |
| **TOTAL (Year 1, no SOC 2)** | **$25K-$80K** | **$30K-$60K** |
| **TOTAL (Year 1, with SOC 2 Type 1)** | **$50K-$130K** | **$30K-$60K** |

## Appendix B: Critical Vendor HIPAA Readiness

| Vendor | HIPAA Ready? | BAA Available? | Action Required |
|--------|-------------|----------------|-----------------|
| Supabase | Yes (with add-on) | Yes (Team plan+) | Upgrade to Team plan, enable HIPAA add-on, sign BAA |
| Anthropic (Claude API) | Yes (with ZDR) | Yes (API only, sales-assisted) | Contact sales, negotiate ZDR + BAA. Claude Desktop is NOT covered. |
| Anthropic (Claude Desktop) | **No** | **No** | Cannot use for PHI. Period. |
| Netlify | **No** | **No** | Cannot host PHI-containing pages. Demo/marketing only. |
| AWS Bedrock (alternative) | Yes | Yes | Alternative path for Claude API with AWS's HIPAA infrastructure. |

## Appendix C: Regulatory Quick Reference

| Regulation | Applies to Ratchet? | Primary Concern |
|------------|---------------------|-----------------|
| HIPAA (Privacy, Security, Breach) | Yes | PHI handling, encryption, access controls, breach notification |
| HITECH Act | Yes | Extends HIPAA to Business Associates, increases penalties |
| FDA SaMD / AI-ML Guidance | Likely no (documentation tool, not diagnostic) | Only if Ratchet crosses into clinical decision support |
| CMS Conditions of Participation | Indirectly | Documentation must meet CMS requirements for reimbursement |
| State AI disclosure laws (CA, TX, IL, CO) | Yes | Patient notification, clinician review mandates |
| 21st Century Cures Act | Indirectly | Interoperability, information blocking (relevant for EMR integration) |
| CCPA/CPRA (California) | Partially | PHI under HIPAA is exempt, but non-PHI data may be covered |

---

## Appendix D: Sources

### HIPAA & Compliance
- [Supabase HIPAA Compliance](https://supabase.com/docs/guides/security/hipaa-compliance)
- [Supabase HIPAA Projects](https://supabase.com/docs/guides/platform/hipaa-projects)
- [Supabase SOC 2 Compliance](https://supabase.com/docs/guides/security/soc-2-compliance)
- [Supabase Shared Responsibility Model](https://supabase.com/docs/guides/deployment/shared-responsibility-model)
- [Supabase Pricing](https://supabase.com/pricing)
- [Is Supabase HIPAA Compliant in 2026?](https://www.accountablehq.com/post/is-supabase-hipaa-compliant-in-2026-baa-phi-and-security-explained)
- [Anthropic BAA for Commercial Customers](https://privacy.claude.com/en/articles/8114513-business-associate-agreements-baa-for-commercial-customers)
- [Anthropic HIPAA-Ready Enterprise Plans](https://support.claude.com/en/articles/13296973-hipaa-ready-enterprise-plans)
- [Is Claude AI HIPAA Compliant? (Paubox)](https://www.paubox.com/blog/is-claude-ai-hipaa-compliant)
- [Claude for Healthcare HIPAA Compliance](https://amitkoth.com/claude-healthcare-hipaa-compliance/)
- [Anthropic Zero Data Retention](https://privacy.claude.com/en/articles/8956058-i-have-a-zero-data-retention-agreement-with-anthropic-what-products-does-it-apply-to)
- [HIPAA Breach Notification Requirements (HIPAA Journal)](https://www.hipaajournal.com/hipaa-breach-notification-requirements/)
- [HIPAA Training Requirements (HIPAA Journal)](https://www.hipaajournal.com/hipaa-training-requirements/)
- [HIPAA Training for Business Associates](https://www.hipaatraining.com/hipaa-training-for-business-associates)

### SOC 2 & HITRUST
- [SOC 2 Cost Breakdown 2025 (Comp AI)](https://trycomp.ai/soc-2-cost-breakdown)
- [SOC 2 Certification Cost 2026 (Bright Defense)](https://www.brightdefense.com/resources/soc-2-certification-cost/)
- [HITRUST vs SOC 2 (RSI Security)](https://blog.rsisecurity.com/whats-the-difference-between-hitrust-and-soc-2-certification/)
- [SOC 2 vs HITRUST (Censinet)](https://censinet.com/perspectives/soc-2-vs-hitrust-choosing-the-right-certification)
- [AccentCare HITRUST Certification](https://www.accentcare.com/accentcare-achieves-hitrust-risk-based-2-year-certification-to-further-mitigate-risk-in-third-party-privacy-security-and-compliance-2/)

### FDA & AI Regulation
- [FDA AI/ML Software as Medical Device](https://www.fda.gov/medical-devices/software-medical-device-samd/artificial-intelligence-software-medical-device)
- [FDA AI Medical Device Regulation 2025 (Complizen)](https://www.complizen.ai/post/fda-ai-medical-device-regulation-2025)
- [FDA Device Guidance Agenda 2026 (Hogan Lovells)](https://www.hoganlovells.com/en/publications/fda-device-guidance-agenda-what-to-watch-in-2026)

### AI Liability & Clinical Safety
- [AI Scribes: Navigating Risks (Nature Digital Medicine)](https://www.nature.com/articles/s41746-025-01895-6)
- [AI Scribes in Health Care (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC12316405/)
- [AI Scribes Pose Liability Risks (MICA)](https://www.mica-insurance.com/blog/posts/ai-scribes-pose-liability-risks/)
- [AI Scribes Risk Management (TMLT)](https://www.tmlt.org/resource/using-ai-medical-scribes-risk-management-considerations)
- [AI in Medical Malpractice (Indigo)](https://www.getindigo.com/blog/ai-in-medical-malpractice-liability-risk-guide)
- [Who's Liable When AI Gets It Wrong? (Medical Economics)](https://www.medicaleconomics.com/view/the-new-malpractice-frontier-who-s-liable-when-ai-gets-it-wrong-)
- [Ambient AI Scribes Privacy and Cybersecurity Risks (ABA)](https://www.americanbar.org/groups/health_law/news/2026/ambient-ai-scribes-privacy-cybersecurity/)

### State AI Regulations
- [Health AI Policy Tracker (Manatt)](https://www.manatt.com/insights/newsletters/health-highlights/manatt-health-health-ai-policy-tracker)
- [47 States Introduced Healthcare AI Bills in 2025 (Becker's)](https://www.beckershospitalreview.com/healthcare-information-technology/ai/47-states-introduced-healthcare-ai-bills-in-2025/)
- [State AI Laws in Healthcare (Akerman)](https://www.akerman.com/en/perspectives/hrx-new-year-new-ai-rules-healthcare-ai-laws-now-in-effect.html)
- [State-Level AI Legislation in Healthcare (Healthcare Law Insights)](https://www.healthcarelawinsights.com/2026/02/shaping-the-future-navigating-state-level-ai-legislation-in-healthcare/)

### EMR Integration
- [HCHB Connect](https://hchb.com/our-solutions/hchb-connect/)
- [HCHB Partner Ecosystem](https://hchb.com/our-solutions/hchb-connect/hchb-partner-ecosystem/)
- [HCHB Custom Integration](https://hchb.com/our-solutions/custom-integration/)
- [Integrating with HCHB (AIR Platform)](https://www.airplatform.io/2023/09/06/hchb-integration/)
- [HCHB Compliance](https://hchb.com/our-solutions/functionality/compliance/)
- [PointClickCare Developer Program](https://developer.pointclickcare.com/spa)
- [PointClickCare FHIR API](https://fhir.pointclickcare.com/)

### CMS & OASIS
- [CMS OASIS Data Sets](https://www.cms.gov/medicare/quality/home-health/oasis-data-sets)
- [CY 2025 Home Health Final Rule (OASIS Answers)](https://oasisanswers.com/cy-2025-home-health-final-rule-finalizes-new-oasis-items-and-more/)
- [AI Tools for OASIS (Home Health Care News)](https://homehealthcarenews.com/2025/06/how-ai-tools-help-home-health-providers-dramatically-lessen-oasis-time-burden/)
- [AI + Human-in-the-Loop for OASIS (MedLearn)](https://icd10monitor.medlearn.com/ai-human-in-the-loop-for-oasis-why-this-hybrid-is-the-only-approach-that-scales/)

### Interoperability Standards
- [HL7 FHIR Overview](https://www.hl7.org/fhir/overview.html)
- [HL7 vs FHIR 2025 (Healthcare Integrations)](https://healthcareintegrations.com/hl7-vs-fhir-which-standard-should-you-prioritize-in-2025/)
- [FHIR Ecosystem (ISP)](https://isp.healthit.gov/fhir-ecosystem)
