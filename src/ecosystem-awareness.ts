/**
 * Ecosystem Awareness — proactive project health monitoring via manifests.
 *
 * Reads project.json manifests from all ST Metro projects, detects stale
 * or unhealthy projects, and surfaces nudges to the user once per day
 * (first conversation only).
 *
 * Follows the Fleet Advisor pattern: init → periodic check → format → send.
 * Uses hive_mind table for nudge tracking (action = 'ecosystem_nudge').
 */

import fs from 'fs';
import path from 'path';
import { logToHiveMind, getHiveMindEntries } from './db.js';
import { logger } from './logger.js';

// ── Types ────────────────────────────────────────────────────────────

interface ProjectManifest {
  name: string;
  display_name: string;
  status: string;
  purpose: string;
  local_path: string;
  health: {
    score: number;
    factors: Record<string, number>;
    last_computed: string;
  };
  activity: {
    last_commit: string;
    commits_30d: number;
    stale_threshold_days: number;
    last_build?: {
      date: string;
      passed: boolean;
      test_count: number;
    };
  };
  nudge: {
    last_nudge: string | null;
    suppressed_until: string | null;
    history: Array<{ date: string; message: string; acknowledged: boolean }>;
  };
  dependencies: Array<{
    project: string;
    relationship: string;
    description: string;
  }>;
}

interface StaleProject {
  name: string;
  displayName: string;
  daysInactive: number;
  healthScore: number;
  status: string;
}

type Sender = (text: string) => Promise<void>;

// ── Configuration ────────────────────────────────────────────────────

const PROJECTS_ROOT = path.join(process.env.HOME || '/home/apexaipc', 'projects');
const CHECK_INTERVAL_MS = 30 * 60 * 1000; // 30 minutes
const STARTUP_DELAY_MS = 2 * 60 * 1000; // 2 minutes after boot
const HEALTH_WARNING_THRESHOLD = 60; // Warn if health drops below this

// ── State ────────────────────────────────────────────────────────────

let send: Sender | null = null;
let checkTimer: ReturnType<typeof setInterval> | null = null;

// ── Initialization ───────────────────────────────────────────────────

export function initEcosystemAwareness(sender: Sender): void {
  send = sender;

  setTimeout(() => {
    void checkAndNudge().catch((err) =>
      logger.error({ err }, 'Initial ecosystem check failed'),
    );
  }, STARTUP_DELAY_MS);

  checkTimer = setInterval(() => {
    void checkAndNudge().catch((err) =>
      logger.error({ err }, 'Ecosystem check failed'),
    );
  }, CHECK_INTERVAL_MS);

  logger.info('Ecosystem Awareness initialized');
}

export function stopEcosystemAwareness(): void {
  if (checkTimer) {
    clearInterval(checkTimer);
    checkTimer = null;
  }
}

// ── Project Discovery ────────────────────────────────────────────────

export function discoverProjects(): ProjectManifest[] {
  const manifests: ProjectManifest[] = [];

  let entries: string[];
  try {
    entries = fs.readdirSync(PROJECTS_ROOT);
  } catch {
    logger.warn('Could not read projects directory: %s', PROJECTS_ROOT);
    return manifests;
  }

  for (const entry of entries) {
    const manifestPath = path.join(PROJECTS_ROOT, entry, 'project.json');
    try {
      if (!fs.existsSync(manifestPath)) continue;
      const raw = fs.readFileSync(manifestPath, 'utf-8');
      const manifest = JSON.parse(raw) as ProjectManifest;
      if (manifest.name && manifest.status) {
        manifests.push(manifest);
      }
    } catch {
      // Skip malformed manifests silently
    }
  }

  return manifests;
}

// ── Staleness Detection ──────────────────────────────────────────────

export function detectIssues(manifests: ProjectManifest[]): StaleProject[] {
  const issues: StaleProject[] = [];
  const now = Date.now();

  for (const m of manifests) {
    // Skip archived/paused projects
    if (m.status === 'archived' || m.status === 'paused') continue;

    // Check suppression
    if (m.nudge?.suppressed_until) {
      const suppressedUntil = new Date(m.nudge.suppressed_until).getTime();
      if (now < suppressedUntil) continue;
    }

    const lastCommit = m.activity?.last_commit
      ? new Date(m.activity.last_commit).getTime()
      : 0;
    const daysInactive = lastCommit
      ? Math.floor((now - lastCommit) / (1000 * 60 * 60 * 24))
      : 999;
    const threshold = m.activity?.stale_threshold_days ?? 14;

    const isStale = daysInactive > threshold;
    const isUnhealthy = m.health?.score < HEALTH_WARNING_THRESHOLD;

    if (isStale || isUnhealthy) {
      issues.push({
        name: m.name,
        displayName: m.display_name || m.name,
        daysInactive,
        healthScore: m.health?.score ?? 0,
        status: m.status,
      });
    }
  }

  // Sort by health score ascending (worst first)
  issues.sort((a, b) => a.healthScore - b.healthScore);

  return issues;
}

// ── Nudge Tracking ───────────────────────────────────────────────────

function wasNudgedToday(): boolean {
  const entries = getHiveMindEntries(10, 'ecosystem');
  const todayStart = new Date();
  todayStart.setHours(0, 0, 0, 0);
  const todayEpoch = Math.floor(todayStart.getTime() / 1000);

  return entries.some(
    (e) => e.action === 'ecosystem_nudge' && e.created_at >= todayEpoch,
  );
}

function recordNudge(projects: StaleProject[], chatId: string): void {
  const summary = projects
    .map((p) => `${p.displayName}: ${p.daysInactive}d inactive, health ${p.healthScore}`)
    .join('; ');

  logToHiveMind('ecosystem', chatId, 'ecosystem_nudge', summary);
}

// ── Message Formatting ───────────────────────────────────────────────

function formatNudge(projects: StaleProject[]): string {
  const lines = projects.map((p) => {
    const icon = p.healthScore < 50 ? '\u{1F534}' : p.healthScore < 70 ? '\u{1F7E1}' : '\u{1F535}';
    const staleNote = p.daysInactive > 0 ? ` — ${p.daysInactive}d since last commit` : '';
    return `${icon} <b>${escapeHtml(p.displayName)}</b> (health: ${p.healthScore})${staleNote}`;
  });

  return [
    '<b>Ecosystem Status</b>',
    '',
    ...lines,
    '',
    '<i>Captain, these projects may require your attention.</i>',
  ].join('\n');
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

// ── Main Check Loop ──────────────────────────────────────────────────

async function checkAndNudge(): Promise<void> {
  if (wasNudgedToday()) {
    logger.debug('Ecosystem nudge already sent today');
    return;
  }

  const manifests = discoverProjects();
  if (manifests.length === 0) {
    logger.debug('No project manifests found');
    return;
  }

  const issues = detectIssues(manifests);
  if (issues.length === 0) {
    logger.debug('All projects healthy');
    return;
  }

  if (!send) return;

  const message = formatNudge(issues);

  try {
    await send(message);
    // Use first ALLOWED_CHAT_ID for recording
    recordNudge(issues, '');
    logger.info({ projectCount: issues.length }, 'Ecosystem nudge sent');
  } catch (err) {
    logger.error({ err }, 'Failed to send ecosystem nudge');
  }
}

// ── Export for /status command ────────────────────────────────────────

export function getEcosystemBriefing(): string {
  const manifests = discoverProjects();
  if (manifests.length === 0) {
    return 'No project manifests found in the ecosystem.';
  }

  const lines: string[] = ['<b>ST Metro Ecosystem Briefing</b>', ''];

  // Sort by health ascending
  const sorted = [...manifests].sort(
    (a, b) => (a.health?.score ?? 0) - (b.health?.score ?? 0),
  );

  for (const m of sorted) {
    const health = m.health?.score ?? 0;
    const icon = health >= 80 ? '\u{2705}' : health >= 60 ? '\u{1F7E1}' : '\u{1F534}';
    const lastCommit = m.activity?.last_commit
      ? new Date(m.activity.last_commit).toLocaleDateString()
      : 'unknown';
    lines.push(
      `${icon} <b>${escapeHtml(m.display_name || m.name)}</b> — health ${health}, last commit ${lastCommit}, ${m.activity?.commits_30d ?? 0} commits/30d`,
    );
  }

  const avgHealth = Math.round(
    sorted.reduce((sum, m) => sum + (m.health?.score ?? 0), 0) / sorted.length,
  );
  lines.push('', `<i>Average ecosystem health: ${avgHealth}/100</i>`);

  return lines.join('\n');
}
