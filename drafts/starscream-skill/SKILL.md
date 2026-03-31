---
name: starscream-content-strategy
description: >
  LinkedIn content strategy engine for Starscream agent. Analyzes post performance data,
  selects optimal topic/type/template combinations, and enforces engagement-driven content
  decisions. Use when drafting LinkedIn posts, reviewing content strategy, or when Starscream
  needs to decide what to write next.
  context: fork
---

# Starscream Content Strategy Engine

Autonomous content strategy layer for Matthew Snow's LinkedIn presence. Reads performance data, applies engagement patterns, and outputs a content decision before any drafting begins.

## Phase 1: Read Performance State

Before writing anything, load the current state:

```bash
# 1. Performance brief (topic-level engagement, what's working/not)
cat /home/apexaipc/projects/claudeclaw/store/starscream_performance_brief.md

# 2. Recent post history (last 10 posts: type, topic, score, date)
python3 -c "
import sqlite3
db = sqlite3.connect('/home/apexaipc/projects/claudeclaw/store/claudeclaw.db')
rows = db.execute('''
  SELECT created_at, post_type, topic, quality_score, named_concept, notes
  FROM post_structure ORDER BY created_at DESC LIMIT 10
''').fetchall()
for r in rows:
    print(f'{r[0]} | {r[1]} | {r[2]} | score:{r[3]} | concept:{r[4]}')
    print(f'  notes: {r[5]}')
"

# 3. Engagement distribution (which topics actually get engagement)
python3 -c "
import sqlite3
db = sqlite3.connect('/home/apexaipc/projects/claudeclaw/store/starscream_analytics.db')
rows = db.execute('''
  SELECT topic, COUNT(*) as posts, AVG(engagement_rate) as avg_eng,
         SUM(impressions) as total_imp, SUM(likes) as total_likes
  FROM post_metrics WHERE topic IS NOT NULL
  GROUP BY topic ORDER BY avg_eng DESC
''').fetchall()
for r in rows:
    print(f'{r[0]}: {r[1]} posts, {r[2]:.1f}% eng, {r[3]} imp, {r[4]} likes')
"
```

## Phase 2: Content Decision Matrix

Apply these rules in order to select today's content:

### Rule 1: Type Rotation
Check `post_structure` for the last 7 days. Enforce rotation:
- INSIGHT: 1/week (teacher voice, name a pattern)
- STORY: 1/week (human voice, personal moment)
- COMIC: bi-weekly (Max the pixel art dev, observer voice)

If a type is overdue, prioritize it. If all are current, pick whichever fits the strongest available angle.

### Rule 2: Topic Selection (Engagement-Weighted)

Rank topics by a composite score: `(avg_engagement * 0.6) + (impression_potential * 0.4)`. Current rankings based on 25-post dataset:

| Priority | Topic | Signal |
|----------|-------|--------|
| 1 | WiFi sensing / ambient intelligence | 4,943 imp spike, +1,488% vs avg. Shock-Reframe template proven here. |
| 2 | Agents vs. workflows / Level 5 autonomy | 1.9% avg engagement (15 posts). Consistent performer. Diversify angles. |
| 3 | Claude Code / MCP / daily workflow | Matthew's core credibility zone. Underexplored on LinkedIn. |
| 4 | AI-powered generalism / human trust layer | New pillar, early signal positive (Calibration Gap post scored 26/30). |
| 5 | Healthcare AI | 0.9% engagement. Niche but differentiating. Use sparingly (1/month). |

**Hard block**: Do NOT post on the same topic as any of the last 3 posts. Check `post_structure` before selecting.

### Rule 3: Template Selection

| Condition | Template |
|-----------|----------|
| Topic has a shocking stat or standard (IEEE, study, etc.) | Shock-Reframe |
| Topic is a walkthrough of something Matthew built | General Skeleton |
| Post type is COMIC | Neither -- use Max format |
| Post type is STORY | General Skeleton (but lead with scene/confession) |

### Rule 4: Zero-Engagement Pattern Avoidance

These opener patterns correlated with 0% engagement across 11 of 25 posts. Hard-block them:

- Generic industry observation openers ("Most teams...", "Everyone's worried about...")
- Abstract threat framing without personal stakes
- Topics where Matthew has no concrete work to reference
- Posts that could be written by anyone in any industry

**Positive signal patterns** (from top 3 posts by engagement):
- Personal pipeline/build experience ("Last Tuesday my build pipeline...")
- Specific autonomy level claims with evidence
- Counterintuitive framing of a known technology

## Phase 3: Output Decision

Before drafting, output a structured content decision:

```
CONTENT DECISION
================
Date: YYYY-MM-DD
Type: INSIGHT | STORY | COMIC
Topic: [specific topic]
Template: General Skeleton | Shock-Reframe | Max Format
Named Concept: [proposed concept name to coin/reference]
Hook Strategy: [1-line description of the opening approach]
Differentiation Check: Last 3 posts were about [X, Y, Z] -- this is different because [reason]
Engagement Prediction: [HIGH/MEDIUM/LOW] based on [pattern match to past performers]
```

Only proceed to drafting after this decision is confirmed.

## Phase 4: Post-Publish Feedback

After publishing, log the decision metadata to `post_structure` for the next cycle:

```sql
INSERT INTO post_structure (
  created_at, post_type, topic, quality_score,
  named_concept, template_used, hook_strategy, notes
) VALUES (
  datetime('now'), 'TYPE', 'topic', SCORE,
  'Concept Name', 'template', 'hook strategy', 'additional notes'
);
```

## Verification

- [ ] Performance brief was read before any content decision
- [ ] Last 10 posts checked for type rotation compliance
- [ ] Last 3 posts checked for topic differentiation
- [ ] Zero-engagement patterns explicitly avoided
- [ ] Content decision output generated before drafting began
- [ ] Named concept identified (signature move)
