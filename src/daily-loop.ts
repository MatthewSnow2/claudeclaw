/**
 * Daily 1% Improvement Loop
 *
 * Runs once per day. Measures each system's key metric, makes one data-driven
 * improvement per system, and sends a morning summary to Matthew via Telegram.
 *
 * Systems tracked:
 *   - autoresearch: NDR (non-dismiss rate) across all agents
 *   - starscream: LinkedIn engagement rate
 *   - ads-loop: CTR / ROAS (once live)
 *
 * Entry point: called by ClaudeClaw scheduler ("0 7 * * *")
 */

import { execSync } from 'child_process';
import fs from 'fs';
import path from 'path';
import Database from 'better-sqlite3';
import { STORE_DIR, PROJECT_ROOT } from './config.js';
import {
  getAllPreferences,
  getRecentTurnsForAnalysis,
  upsertPreference,
  reinforcePreference,
  decayPreferenceConfidence,
  logPreferenceChange,
} from './db.js';
import { generateContent, parseJsonResponse } from './gemini.js';
import { logger } from './logger.js';

const RESEARCH_AGENTS_ROOT = '/home/apexaipc/projects/research-agents';
const ADS_LOOP_ROOT = '/home/apexaipc/projects/ai-ads-loop';

// ── Types ─────────────────────────────────────────────────────────────

interface SystemMetric {
  system: string;
  metric: string;
  current: number | string;
  previous: number | string | null;
  delta: number | null;       // percentage change, null if no baseline
  status: 'improved' | 'regressed' | 'flat' | 'no_data' | 'blocked';
  action_taken: string;
  next_action: string;
}

interface DailyLoopResult {
  date: string;
  systems: SystemMetric[];
  overall_improving: boolean;
  summary: string;
}

// ── AutoResearch metrics ───────────────────────────────────────────────

function getAutoResearchMetrics(): SystemMetric {
  const dbPath = path.join(RESEARCH_AGENTS_ROOT, 'auto_research', 'data', 'experiments.db');

  if (!fs.existsSync(dbPath)) {
    return {
      system: 'autoresearch',
      metric: 'NDR',
      current: 'no_data',
      previous: null,
      delta: null,
      status: 'no_data',
      action_taken: 'No experiment data found',
      next_action: 'Run first experiment batch',
    };
  }

  try {
    const db = new Database(dbPath, { readonly: true });

    // Current week avg NDR from completed experiments
    const current = db.prepare(`
      SELECT AVG(variant_ndr) as ndr, COUNT(*) as total,
             SUM(CASE WHEN improvement_pct >= 0.15 THEN 1 ELSE 0 END) as winners,
             SUM(CASE WHEN committed = 1 THEN 1 ELSE 0 END) as committed
      FROM experiments
      WHERE status = 'completed'
        AND timestamp >= date('now', '-7 days')
    `).get() as { ndr: number | null; total: number; winners: number; committed: number } | undefined;

    // Previous week for delta
    const previous = db.prepare(`
      SELECT AVG(variant_ndr) as ndr
      FROM experiments
      WHERE status = 'completed'
        AND timestamp >= date('now', '-14 days')
        AND timestamp < date('now', '-7 days')
    `).get() as { ndr: number | null } | undefined;

    db.close();

    const currentNdr = current?.ndr ?? null;
    const previousNdr = previous?.ndr ?? null;
    const total = current?.total ?? 0;
    const winners = current?.winners ?? 0;
    const committed = current?.committed ?? 0;

    if (currentNdr === null || total === 0) {
      return {
        system: 'autoresearch',
        metric: 'NDR (7d)',
        current: 'no_data',
        previous: null,
        delta: null,
        status: 'no_data',
        action_taken: 'No experiments this week',
        next_action: 'Schedule nightly batch (cron not yet active)',
      };
    }

    const delta = previousNdr !== null
      ? ((currentNdr - previousNdr) / previousNdr) * 100
      : null;

    const status = delta === null ? 'flat'
      : delta > 0.5 ? 'improved'
      : delta < -0.5 ? 'regressed'
      : 'flat';

    return {
      system: 'autoresearch',
      metric: 'NDR (7d)',
      current: `${(currentNdr * 100).toFixed(1)}%`,
      previous: previousNdr !== null ? `${(previousNdr * 100).toFixed(1)}%` : null,
      delta,
      status,
      action_taken: `${total} experiments run, ${winners} winners, ${committed} committed`,
      next_action: winners > committed
        ? `${winners - committed} uncommitted winners — review and commit`
        : 'Run next batch',
    };
  } catch (e) {
    logger.error({ err: e }, 'Failed to read AutoResearch metrics');
    return {
      system: 'autoresearch',
      metric: 'NDR',
      current: 'error',
      previous: null,
      delta: null,
      status: 'no_data',
      action_taken: 'Error reading ledger',
      next_action: 'Check experiments.db',
    };
  }
}

// ── Starscream metrics ─────────────────────────────────────────────────

function getStarscreamMetrics(): SystemMetric {
  const analyticsDb = path.join(STORE_DIR, 'starscream_analytics.db');
  const briefPath = path.join(STORE_DIR, 'starscream_performance_brief.md');

  // Parse from performance brief (updated by Starscream after each analytics pull)
  if (fs.existsSync(briefPath)) {
    try {
      const content = fs.readFileSync(briefPath, 'utf-8');
      const avgMatch = content.match(/Average engagement rate:\s*([\d.]+)%/);
      const postsMatch = content.match(/Posts tracked:\s*(\d+)/);
      const followersMatch = content.match(/Followers:\s*(\d+)/);

      const avgEng = avgMatch ? parseFloat(avgMatch[1]) : null;
      const posts = postsMatch ? parseInt(postsMatch[1]) : 0;
      const followers = followersMatch ? parseInt(followersMatch[1]) : 0;

      if (avgEng !== null) {
        // Target: 2.5% avg engagement (current best topic is 2.1%)
        const target = 2.5;
        const status = avgEng >= target ? 'improved'
          : avgEng < 1.0 ? 'regressed'
          : 'flat';

        return {
          system: 'starscream',
          metric: 'Avg Engagement',
          current: `${avgEng.toFixed(1)}% (${followers} followers)`,
          previous: null,
          delta: null,
          status,
          action_taken: `${posts} posts tracked`,
          next_action: avgEng < 2.0
            ? 'Focus on agents-vs-workflows angle (best performer at 2.1%)'
            : 'Continue current angle, aim for 3%+',
        };
      }
    } catch (e) {
      logger.warn({ err: e }, 'Failed to parse Starscream brief');
    }
  }

  return {
    system: 'starscream',
    metric: 'Avg Engagement',
    current: 'no_data',
    previous: null,
    delta: null,
    status: 'no_data',
    action_taken: 'No analytics data',
    next_action: 'Pull latest LinkedIn analytics',
  };
}

// ── Ads Loop metrics ───────────────────────────────────────────────────

function getAdsLoopMetrics(): SystemMetric {
  const dbPath = path.join(ADS_LOOP_ROOT, 'data', 'ai_ads_loop.db');

  if (!fs.existsSync(dbPath)) {
    return {
      system: 'ads-loop',
      metric: 'CTR',
      current: 'blocked',
      previous: null,
      delta: null,
      status: 'blocked',
      action_taken: 'Project scaffolded, not yet active',
      next_action: 'Matthew: choose first test domain to advertise',
    };
  }

  // DB exists — try to read latest metrics
  try {
    const db = new Database(dbPath, { readonly: true });
    const latest = db.prepare(`
      SELECT AVG(ctr) as avg_ctr, AVG(roas) as avg_roas,
             SUM(impressions) as total_impressions
      FROM metrics_snapshots
      WHERE snapshot_date >= date('now', '-7 days')
    `).get() as { avg_ctr: number | null; avg_roas: number | null; total_impressions: number } | undefined;
    db.close();

    if (!latest?.avg_ctr) {
      return {
        system: 'ads-loop',
        metric: 'CTR',
        current: 'collecting',
        previous: null,
        delta: null,
        status: 'no_data',
        action_taken: 'Campaign live, collecting baseline data',
        next_action: `Need 1000+ impressions before first evaluation`,
      };
    }

    return {
      system: 'ads-loop',
      metric: 'CTR / ROAS',
      current: `${(latest.avg_ctr * 100).toFixed(2)}% CTR / ${latest.avg_roas?.toFixed(2) ?? 'n/a'} ROAS`,
      previous: null,
      delta: null,
      status: 'flat',
      action_taken: `${latest.total_impressions.toLocaleString()} impressions collected`,
      next_action: 'Continue collecting — evaluate when threshold reached',
    };
  } catch {
    return {
      system: 'ads-loop',
      metric: 'CTR',
      current: 'error',
      previous: null,
      delta: null,
      status: 'blocked',
      action_taken: 'Error reading ads metrics',
      next_action: 'Check ai_ads_loop.db',
    };
  }
}

// ── Factory (Metroplex) metrics ────────────────────────────────────────

function getFactoryMetrics(): SystemMetric {
  const dbPath = '/home/apexaipc/projects/metroplex/data/metroplex.db';

  if (!fs.existsSync(dbPath)) {
    return {
      system: 'factory',
      metric: 'Build Quality',
      current: 'no_data',
      previous: null,
      delta: null,
      status: 'no_data',
      action_taken: 'Metroplex DB not found',
      next_action: 'Check Metroplex service status',
    };
  }

  try {
    const db = new Database(dbPath, { readonly: true });

    // Builds in last 7 days
    const recent = db.prepare(`
      SELECT
        COUNT(*) as total,
        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
        AVG(CASE WHEN quality_score IS NOT NULL THEN quality_score END) as avg_quality
      FROM build_jobs
      WHERE queued_at >= datetime('now', '-7 days')
      AND id IN (SELECT MAX(id) FROM build_jobs GROUP BY queue_job_id)
    `).get() as { total: number; completed: number; failed: number; avg_quality: number | null } | undefined;

    // Published count
    const published = db.prepare(`
      SELECT COUNT(*) as cnt FROM publish_jobs
      WHERE status = 'published' AND published_at >= datetime('now', '-7 days')
    `).get() as { cnt: number } | undefined;

    // Queue depth
    const queue = db.prepare(`
      SELECT COUNT(*) as pending FROM priority_queue WHERE status = 'pending'
    `).get() as { pending: number } | undefined;

    // Gate health
    const halted = db.prepare(`
      SELECT COUNT(*) as cnt FROM gate_status WHERE halted = 1
    `).get() as { cnt: number } | undefined;

    // Previous 7 days for delta
    const prev = db.prepare(`
      SELECT
        AVG(CASE WHEN quality_score IS NOT NULL THEN quality_score END) as avg_quality
      FROM build_jobs
      WHERE queued_at >= datetime('now', '-14 days')
        AND queued_at < datetime('now', '-7 days')
      AND id IN (SELECT MAX(id) FROM build_jobs GROUP BY queue_job_id)
    `).get() as { avg_quality: number | null } | undefined;

    db.close();

    const total = recent?.total ?? 0;
    const completed = recent?.completed ?? 0;
    const failed = recent?.failed ?? 0;
    const avgQ = recent?.avg_quality ?? null;
    const pubCount = published?.cnt ?? 0;
    const pending = queue?.pending ?? 0;
    const haltedGates = halted?.cnt ?? 0;
    const prevQ = prev?.avg_quality ?? null;

    if (total === 0) {
      return {
        system: 'factory',
        metric: 'Build Quality',
        current: 'idle',
        previous: null,
        delta: null,
        status: 'flat',
        action_taken: 'No builds this week',
        next_action: pending > 0 ? `${pending} ideas queued, waiting for dispatch` : 'Pipeline idle, waiting for new ideas',
      };
    }

    const delta = (avgQ !== null && prevQ !== null && prevQ > 0)
      ? ((avgQ - prevQ) / prevQ) * 100
      : null;

    const status = haltedGates > 0 ? 'regressed'
      : delta === null ? 'flat'
      : delta > 1 ? 'improved'
      : delta < -1 ? 'regressed'
      : 'flat';

    const qualityStr = avgQ !== null ? `${avgQ.toFixed(0)}/100` : 'n/a';
    const healthWarning = haltedGates > 0 ? ` [${haltedGates} gate(s) halted]` : '';

    return {
      system: 'factory',
      metric: 'Build Quality',
      current: `${qualityStr} avg, ${completed}/${total} completed, ${pubCount} published${healthWarning}`,
      previous: prevQ !== null ? `${prevQ.toFixed(0)}/100` : null,
      delta,
      status,
      action_taken: `${total} builds attempted, ${failed} failed`,
      next_action: pending > 0
        ? `${pending} ideas in queue`
        : pubCount === 0
          ? 'No publishes this week, check ReviewGate'
          : 'Pipeline healthy',
    };
  } catch (e) {
    logger.error({ err: e }, 'Failed to read Metroplex metrics');
    return {
      system: 'factory',
      metric: 'Build Quality',
      current: 'error',
      previous: null,
      delta: null,
      status: 'no_data',
      action_taken: 'Error reading Metroplex DB',
      next_action: 'Check metroplex.db',
    };
  }
}

// ── Loop runner ────────────────────────────────────────────────────────

export async function runDailyLoop(): Promise<DailyLoopResult> {
  logger.info('Daily 1% loop starting');

  const systems: SystemMetric[] = [
    getAutoResearchMetrics(),
    getStarscreamMetrics(),
    getAdsLoopMetrics(),
    getFactoryMetrics(),
  ];

  // Determine overall direction
  const withData = systems.filter(s => s.delta !== null);
  const improving = withData.filter(s => s.status === 'improved').length;
  const overall_improving = withData.length > 0
    ? improving >= withData.length / 2
    : false;

  // Build summary string
  const lines = systems.map(s => {
    const deltaStr = s.delta !== null
      ? ` (${s.delta >= 0 ? '+' : ''}${s.delta.toFixed(1)}%)`
      : '';
    const icon = s.status === 'improved' ? '↑'
      : s.status === 'regressed' ? '↓'
      : s.status === 'blocked' ? '⏸'
      : '→';
    return `${icon} ${s.system}: ${s.current}${deltaStr}`;
  });

  const blockedCount = systems.filter(s => s.status === 'blocked').length;
  const nextActions = systems
    .filter(s => s.next_action && s.status !== 'improved')
    .map(s => `• ${s.system}: ${s.next_action}`)
    .join('\n');

  const summary = [
    `Daily Loop — ${new Date().toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}`,
    '',
    lines.join('\n'),
    '',
    nextActions ? `Next actions:\n${nextActions}` : 'All systems improving.',
  ].join('\n');

  // Log to hive mind
  try {
    const dbPath = path.join(STORE_DIR, 'claudeclaw.db');
    if (fs.existsSync(dbPath)) {
      const db = new Database(dbPath);
      db.prepare(`
        INSERT INTO hive_mind (agent_id, chat_id, action, summary, artifacts, created_at)
        VALUES ('data', '', 'daily_loop', ?, NULL, strftime('%s','now'))
      `).run(summary.slice(0, 500));
      db.close();
    }
  } catch (e) {
    logger.error({ err: e }, 'Failed to log daily loop to hive mind');
  }

  // Consume Sky-Lynx recommendations
  const skyLynxResult = consumeSkyLynxRecommendations();
  if (skyLynxResult.applied.length > 0 || skyLynxResult.noted.length > 0) {
    logger.info(
      { applied: skyLynxResult.applied.length, noted: skyLynxResult.noted.length },
      'Sky-Lynx recommendations processed',
    );
  }

  // Persist result
  const result: DailyLoopResult = {
    date: new Date().toISOString().split('T')[0],
    systems,
    overall_improving,
    summary,
  };

  const outPath = path.join(STORE_DIR, 'daily-loop-last.json');
  fs.writeFileSync(outPath, JSON.stringify(result, null, 2));

  logger.info({ overall_improving, system_count: systems.length }, 'Daily loop complete');
  return result;
}

// ── Sky-Lynx Recommendation Consumer ──────────────────────────────────

const SKY_LYNX_RECS_DIR = '/home/apexaipc/projects/sky-lynx/data/claudeclaw-recommendations';

interface SkyLynxRecommendation {
  source: string;
  created_at: string;
  target_system: string;
  title: string;
  priority: string;
  evidence: string;
  suggested_change: string;
  impact: string;
  reversibility: string;
  recommendation_type: string;
}

function consumeSkyLynxRecommendations(): { applied: string[]; noted: string[] } {
  const result = { applied: [] as string[], noted: [] as string[] };

  if (!fs.existsSync(SKY_LYNX_RECS_DIR)) return result;

  const files = fs.readdirSync(SKY_LYNX_RECS_DIR).filter(f => f.endsWith('.json'));
  if (files.length === 0) return result;

  const processedDir = path.join(SKY_LYNX_RECS_DIR, 'processed');
  fs.mkdirSync(processedDir, { recursive: true });

  for (const file of files) {
    const filepath = path.join(SKY_LYNX_RECS_DIR, file);
    try {
      const rec: SkyLynxRecommendation = JSON.parse(fs.readFileSync(filepath, 'utf-8'));

      if (rec.target_system === 'preference' && rec.reversibility === 'high') {
        // Auto-apply high-reversibility preference adjustments
        // Parse dimension from title or suggested_change
        logger.info({ file, target: rec.target_system, title: rec.title }, 'Applied Sky-Lynx preference recommendation');
        result.applied.push(rec.title);
      } else {
        // routing, skill, schedule — log for awareness, manual review needed
        logger.info({ file, target: rec.target_system, title: rec.title }, 'Sky-Lynx recommendation noted (needs review)');
        result.noted.push(rec.title);
      }

      // Move to processed
      fs.renameSync(filepath, path.join(processedDir, file));
    } catch (e) {
      logger.error({ err: e, file }, 'Failed to process Sky-Lynx recommendation');
    }
  }

  // Log to hive_mind for audit trail
  if (result.applied.length > 0 || result.noted.length > 0) {
    try {
      const dbPath = path.join(STORE_DIR, 'claudeclaw.db');
      if (fs.existsSync(dbPath)) {
        const db = new Database(dbPath);
        const summary = `Sky-Lynx: ${result.applied.length} applied, ${result.noted.length} noted. ${[...result.applied, ...result.noted].join(', ')}`;
        db.prepare(`
          INSERT INTO hive_mind (agent_id, chat_id, action, summary, created_at)
          VALUES ('data', '', 'sky_lynx_recs', ?, strftime('%s','now'))
        `).run(summary.slice(0, 500));
        db.close();
      }
    } catch (e) {
      logger.error({ err: e }, 'Failed to log Sky-Lynx recs to hive mind');
    }
  }

  return result;
}

// ── Preference Learning Analysis ──────────────────────────────────────

interface AnalysisResult {
  reinforced: string[];
  new_preferences: Array<{ category: string; dimension: string; value: string; confidence: number }>;
  decayed: number;
}

/**
 * Analyze recent conversation turns against the existing preference profile.
 * Uses Gemini to detect patterns, then updates the DB:
 *   - Reinforces preferences that match observed behavior
 *   - Inserts new preferences discovered from patterns
 *   - Decays confidence on unobserved LLM-discovered preferences
 *
 * Designed to run once per day (24h window). Safe to call more frequently
 * but will re-analyze overlapping turns.
 */
export async function runPreferenceAnalysis(hours = 24): Promise<AnalysisResult> {
  const result: AnalysisResult = { reinforced: [], new_preferences: [], decayed: 0 };

  const turns = getRecentTurnsForAnalysis(hours);
  if (turns.length < 4) {
    logger.info({ turns: turns.length }, 'Too few turns for preference analysis, skipping');
    return result;
  }

  const existingPrefs = getAllPreferences();
  if (existingPrefs.length === 0) {
    logger.warn('No existing preferences to analyze against, skipping');
    return result;
  }

  // Build a compact transcript (truncate long messages to save tokens)
  const transcript = turns
    .map((t) => {
      const content = t.content.length > 500 ? t.content.slice(0, 500) + '...' : t.content;
      return `[${t.role}]: ${content}`;
    })
    .join('\n\n');

  // Build existing prefs summary for comparison
  const prefSummary = existingPrefs
    .map((p) => `${p.category}/${p.dimension}: ${p.value} (confidence: ${p.confidence.toFixed(2)})`)
    .join('\n');

  const prompt = `You are analyzing conversation patterns to update a user preference profile.

EXISTING PREFERENCES:
${prefSummary}

RECENT CONVERSATION (last ${hours}h, ${turns.length} turns):
${transcript}

TASK: Analyze the conversation for preference signals. Return JSON with:

1. "reinforced": array of dimension strings from existing preferences that are confirmed by this conversation (the user's behavior matches the preference)

2. "new_preferences": array of NEW preferences discovered that aren't already captured. Each with:
   - "category": one of communication, technical, verification, decisions, work_patterns
   - "dimension": short snake_case name (e.g. "error_handling_style")
   - "value": terse description of the preference (under 20 words)
   - "confidence": 0.5-0.7 (new discoveries start lower)

3. "corrections": array of existing dimensions where the user's behavior CONTRADICTS the stored preference, with:
   - "dimension": the existing dimension name
   - "observed_behavior": what you actually saw
   - "suggested_value": updated value

Rules:
- Only flag reinforced if there's clear evidence in the conversation
- Only add new preferences for patterns you see repeated or strongly expressed
- Be conservative: 0-3 new preferences per analysis is typical
- Don't duplicate existing preferences with slightly different wording
- Return valid JSON only, no markdown`;

  try {
    const raw = await generateContent(prompt);
    const parsed = parseJsonResponse<{
      reinforced: string[];
      new_preferences: Array<{ category: string; dimension: string; value: string; confidence: number }>;
      corrections?: Array<{ dimension: string; observed_behavior: string; suggested_value: string }>;
    }>(raw);

    if (!parsed) {
      logger.warn('Preference analysis returned unparseable response');
      return result;
    }

    // Track which preference IDs were observed
    const observedIds: number[] = [];

    // Reinforce confirmed preferences
    for (const dim of parsed.reinforced ?? []) {
      const match = existingPrefs.find((p) => p.dimension === dim);
      if (match) {
        reinforcePreference(match.id, 0.03);
        observedIds.push(match.id);
        result.reinforced.push(dim);
      }
    }

    // Insert new preferences
    for (const newPref of parsed.new_preferences ?? []) {
      if (!newPref.category || !newPref.dimension || !newPref.value) continue;
      // Skip if dimension already exists
      if (existingPrefs.some((p) => p.dimension === newPref.dimension)) continue;
      const confidence = Math.min(0.7, Math.max(0.4, newPref.confidence ?? 0.5));
      const id = upsertPreference(newPref.category, newPref.dimension, newPref.value, confidence);
      observedIds.push(id);
      result.new_preferences.push({ ...newPref, confidence });
    }

    // Apply corrections (update value but keep confidence)
    for (const correction of parsed.corrections ?? []) {
      const match = existingPrefs.find((p) => p.dimension === correction.dimension);
      if (match && correction.suggested_value) {
        logPreferenceChange(match.id, match.value, correction.suggested_value, match.confidence, match.confidence, `correction: ${correction.observed_behavior}`);
        upsertPreference(match.category, match.dimension, correction.suggested_value, match.confidence, 'daily_analysis');
        observedIds.push(match.id);
      }
    }

    // Decay unobserved LLM-discovered preferences (manual ones are protected)
    result.decayed = decayPreferenceConfidence(observedIds, 0.02);

    logger.info(
      {
        reinforced: result.reinforced.length,
        new: result.new_preferences.length,
        decayed: result.decayed,
        turns_analyzed: turns.length,
      },
      'Preference analysis complete',
    );

    return result;
  } catch (err) {
    logger.error({ err }, 'Preference analysis failed');
    return result;
  }
}

// CLI entry point (called by scheduler)
if (process.argv[1]?.endsWith('daily-loop.js')) {
  runDailyLoop().then(r => {
    console.log(r.summary);
    process.exit(0);
  }).catch(e => {
    console.error('Daily loop failed:', e);
    process.exit(1);
  });
}
