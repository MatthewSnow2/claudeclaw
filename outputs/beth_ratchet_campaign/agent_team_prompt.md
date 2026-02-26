# Agent Team Prompt: Beth/Ratchet Go-to-Market Campaign

## Directive

Create an agent team to design and execute a comprehensive go-to-market campaign for Ratchet, an AI-powered virtual assistant that eliminates administrative burden for home health nurses by enabling voice-driven EMR documentation through PointCare.

## Context

**Product**: Ratchet -- an MCP (Model Context Protocol) tool that lets home health nurses document patient visits using natural language conversation instead of manual EMR data entry.

**How it works**: Nurse speaks naturally about the visit -> Claude Desktop + Ratchet MCP generates a structured SOAP note with vitals, interventions, education, and care plan -> Data syncs to Supabase backend -> Real-time EMR dashboard shows updates with field highlights.

**Current state**:
- Fully functional with mock PointCare EMR APIs
- Three core tools: `search_patient`, `create_visit_note`, `get_patient_history`
- Supports all visit types: skilled nursing, PT, OT, speech therapy, home health aide, social work
- Captures complete clinical data: vitals (BP, HR, temp, O2, pain, respiratory rate, weight), SOAP notes, interventions, education, care plans
- Live demo dashboard: https://pointcare-emr-demo.netlify.app
- GitHub repos: m2ai-mcp-servers/mcp-pointcare-ratchet, m2ai-mcp-servers/pointcare-emr-dashboard
- Built by M2AI (Matthew Snow's AI consultancy)

**Target EMR ecosystem**:
- **AccentCare** uses HCHB (Homecare Homebase) as back-office EMR
- **PointCare** is AccentCare's mobile app for field clinicians (Android)
- Ratchet sits alongside PointCare -- it doesn't replace it, it makes documentation faster

**Proven value**: Nurses who have used the system report significant time savings on admin work -- the #1 complaint in home health nursing. Documentation that takes 15-20 minutes per visit manually can be completed in 2-3 minutes via voice.

**Problem**: Email outreach to PointCare yielded no response. Need alternative approaches to reach decision-makers AND identify other organizations in the home health space that would benefit.

**Company**: M2AI -- AI consultancy run by Matthew Snow. Focus on building AI-powered tools and autonomous systems. Based in Nashville, TN area.

## Inputs

Reference material for agents:
- Product architecture: Review the Ratchet MCP tool structure (3 tools, SOAP note format, visit types, vital signs schema)
- Demo assets: Live dashboard at https://pointcare-emr-demo.netlify.app
- Market context: Home health nursing industry, EMR documentation pain points, AccentCare/HCHB/PointCare ecosystem
- Competitor landscape: Other voice-to-EMR solutions, AI documentation tools in healthcare

## Team

Spawn 5 teammates:

### 1. Market Researcher
**Mission**: Map the home health EMR ecosystem comprehensively. Identify who uses PointCare/HCHB, what competing EMR systems exist in home health, which organizations have the biggest documentation pain, and where the buying decisions happen. Determine total addressable market for AI-assisted documentation in home health.

**Deliverable**:
- Home health EMR market map (key players, market share, growth trends)
- PointCare/AccentCare organizational structure (who makes integration/partnership decisions)
- List of 10-15 target organizations using PointCare or similar home health EMRs
- Competitor analysis: existing AI documentation solutions in healthcare (Nuance DAX, Abridge, Suki, DeepScribe, etc.) -- features, pricing, market position
- Market sizing: TAM/SAM/SOM for AI-assisted home health documentation
- Save to `outputs/beth_ratchet_campaign/market_research.md`

### 2. Partnership Strategist
**Mission**: Design a multi-channel approach to reach PointCare/AccentCare decision-makers AND identify alternative partnership paths. Email failed -- what works? Map the human network: LinkedIn connections, mutual contacts, conference encounters, channel partners, industry advisors. Also identify if going through AccentCare corporate, PointCare product team, or regional AccentCare offices is the best entry point.

**Deliverable**:
- PointCare/AccentCare decision-maker map (roles, names if findable via LinkedIn, organizational hierarchy)
- 5 alternative outreach strategies ranked by likelihood of success (LinkedIn warm intros, conference booths, nursing association partnerships, AccentCare regional offices, healthcare IT intermediaries)
- Channel partner opportunities (healthcare IT consultants, EMR integration partners, nursing staffing agencies)
- Strategic partnership pitch: what does M2AI offer PointCare? (reduce documentation time = higher nurse satisfaction = lower turnover = AccentCare saves money)
- Cold outreach templates that aren't email (LinkedIn DM, conference follow-up, mutual connection intro request)
- Save to `outputs/beth_ratchet_campaign/partnership_strategy.md`

### 3. Campaign Architect
**Mission**: Build a full product awareness campaign with specific channels, messaging, content calendar, and social proof strategy. Target both top-down (PointCare/AccentCare execs) and bottom-up (nurses who would champion the tool internally). Design content that demonstrates the before/after of nurse documentation workflow.

**Deliverable**:
- Campaign strategy document with:
  - Messaging framework: headline, value prop, proof points, objection handling
  - Channel strategy: LinkedIn (organic + ads), nursing forums (allnurses.com, r/nursing), healthcare IT publications, YouTube demo videos, podcast appearances
  - Content calendar: 90-day plan with weekly content themes
  - Social proof strategy: how to capture and amplify nurse testimonials, before/after time comparisons, case study format
  - Bottom-up strategy: how to get individual nurses excited enough to champion this to their managers
  - Top-down strategy: how to position this for C-suite at home health agencies (ROI focus: reduced documentation time, nurse retention, compliance)
  - Demo/video script: 2-minute walkthrough showing voice-to-SOAP-note workflow
  - Conference strategy: which healthcare/nursing conferences to attend or sponsor (NAHC, Home Health Line, state HHA conferences)
- Save to `outputs/beth_ratchet_campaign/campaign_plan.md`

### 4. Healthcare Compliance Reviewer
**Mission**: Identify every regulatory, compliance, and legal consideration that affects go-to-market. What does M2AI need to have in place before approaching healthcare organizations? What are the deal-breakers that would make a health system say no? What certifications, agreements, or policies are required?

**Deliverable**:
- Compliance checklist:
  - HIPAA: BAA requirements, PHI handling, data storage, encryption
  - SOC 2: Is it required? Type 1 vs Type 2? Timeline and cost
  - State regulations: Any state-specific home health documentation requirements?
  - AI in healthcare: FDA guidance on clinical AI tools, CMS documentation requirements
  - EMR integration requirements: What does PointCare/HCHB require for third-party integrations? API access policies?
  - Data residency: Where is data stored? (Currently Supabase -- is that acceptable for PHI?)
  - Liability: If the AI generates an incorrect note, who is liable?
- Risk assessment: What are the top 5 compliance risks and mitigations?
- "Table stakes" list: What MUST be done before approaching any healthcare organization?
- Save to `outputs/beth_ratchet_campaign/compliance_review.md`

### 5. Devil's Advocate
**Mission**: Challenge the entire campaign. Poke holes in the strategy. Find the reasons this could fail. Ask the hard questions nobody wants to ask.

**Key challenges to address**:
- "Nurses don't use Claude Desktop." -- The current delivery mechanism requires Claude Desktop on a laptop. Home health nurses use tablets/phones in the field running PointCare mobile app. How does Ratchet actually get to nurses in their real workflow?
- "Mock APIs aren't a product." -- Ratchet works with mock PointCare data. Without real API access, what are you actually selling? A demo?
- "PointCare won't respond because they don't need you." -- PointCare/AccentCare could build this themselves. Why would they partner with a one-person consultancy?
- "The compliance burden will kill this." -- HIPAA, SOC 2, BAAs, liability. Can a small shop handle this?
- "Voice documentation already exists." -- Nuance DAX, Dragon Medical, Suki, Abridge. They have funding, sales teams, and hospital system contracts. What's the competitive moat?
- "Is this the beachhead or a distraction?" -- M2AI's core is AI consulting tools (ST Metro, SCM). Is healthcare a commitment or a side project?

**Deliverable**:
- Numbered objections with severity ratings (Fatal / Serious / Manageable)
- For each objection: the assumption being challenged, why it might be wrong, what happens if it IS wrong
- "Kill criteria": Under what circumstances should Matthew abandon this and focus elsewhere?
- "De-risk" recommendations: What are the minimum viable steps to validate before investing further?
- Save to `outputs/beth_ratchet_campaign/devils_advocate.md`

## Dependencies

**Execution order**: Parallel fan-out with post-completion synthesis.

- Agents 1-4 work in parallel (no dependencies between them)
- Agent 5 (Devil's Advocate) should read all other agents' outputs before writing
- However, for efficiency, Agent 5 can work in parallel and challenge the INPUTS and ASSUMPTIONS rather than waiting for other agents' specific findings

## Coordination

- Each agent operates independently within their domain
- No agent should duplicate another's work -- each has a distinct deliverable
- If an agent discovers something critical to another agent's domain, note it in a "Cross-References" section at the end of their deliverable
- The Devil's Advocate should explicitly reference and challenge findings from other agents where applicable

## Synthesis

After all 5 agents complete:

1. Cross-reference findings for contradictions (e.g., Campaign Architect says "go to conferences" but Compliance Reviewer says "you can't demo with real data yet")
2. Identify gaps: critical questions no agent addressed
3. Rank all recommendations by:
   - Impact (how much does this move the needle?)
   - Effort (how much time/money does this take?)
   - Urgency (is this time-sensitive?)
4. Produce a consolidated campaign plan with:
   - Executive summary (what to do in the next 30/60/90 days)
   - Phase 1 actions (this week): immediate, zero-cost moves
   - Phase 2 actions (this month): moderate effort, validates assumptions
   - Phase 3 actions (next quarter): significant investment, scales if validated
   - Decision gates: what must be true before advancing to each phase
   - Budget estimate (rough) for each phase
   - Kill criteria: when to stop and redirect effort

Save consolidated plan to `outputs/beth_ratchet_campaign/consolidated_campaign_plan.md`

## Output

Final deliverables (6 files):
```
outputs/beth_ratchet_campaign/
  market_research.md
  partnership_strategy.md
  campaign_plan.md
  compliance_review.md
  devils_advocate.md
  consolidated_campaign_plan.md
```
