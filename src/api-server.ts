/**
 * Pipeline API Server
 *
 * Serves the dashboard static files AND provides write endpoints
 * for pipeline item management (reorder, move between lanes, kill).
 *
 * Replaces the previous `python3 -m http.server 8080` process.
 */

import express from 'express';
import path from 'path';
import { exec } from 'child_process';
import { fileURLToPath } from 'url';

import {
  initDatabase,
  getPipelineItems,
  updatePipelineStatus,
  updatePipelineOrder,
  getAllScheduledTasks,
  deleteScheduledTask,
  pauseScheduledTask,
  resumeScheduledTask,
  getHiveMindEntries,
} from './db.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PORT = parseInt(process.env.PORT || '8080', 10);
const PROJECT_ROOT = path.resolve(__dirname, '..');
const DASHBOARD_DIR = path.join(PROJECT_ROOT, 'dashboard');

// Initialize DB (runs migrations including sort_order)
initDatabase();

const app = express();
app.use(express.json());

// ── API Routes ──────────────────────────────────────────────────────

/** GET /api/pipeline - Live pipeline data from DB */
app.get('/api/pipeline', (_req, res) => {
  try {
    const items = getPipelineItems();
    res.json({ ok: true, items });
  } catch (err) {
    res.status(500).json({ ok: false, error: String(err) });
  }
});

/** PATCH /api/pipeline/:id/status - Move item between lanes */
app.patch('/api/pipeline/:id/status', (req, res) => {
  const { id } = req.params;
  const { status, reason } = req.body;

  if (!status || typeof status !== 'string') {
    res.status(400).json({ ok: false, error: 'status is required' });
    return;
  }

  try {
    const updated = updatePipelineStatus(id, status, reason, 'dashboard');
    if (!updated) {
      res.status(404).json({ ok: false, error: 'Item not found or invalid status' });
      return;
    }

    regenerateReport();
    res.json({ ok: true, item: updated });
  } catch (err) {
    res.status(500).json({ ok: false, error: String(err) });
  }
});

/** PATCH /api/pipeline/order - Reorder items within a lane */
app.patch('/api/pipeline/order', (req, res) => {
  const { items } = req.body;

  if (!Array.isArray(items)) {
    res.status(400).json({ ok: false, error: 'items array is required' });
    return;
  }

  try {
    updatePipelineOrder(items);
    regenerateReport();
    res.json({ ok: true });
  } catch (err) {
    res.status(500).json({ ok: false, error: String(err) });
  }
});

// ── Scheduled Tasks API ─────────────────────────────────────────────

/** GET /api/tasks - All scheduled tasks */
app.get('/api/tasks', (_req, res) => {
  try {
    const tasks = getAllScheduledTasks();
    res.json({ ok: true, tasks });
  } catch (err) {
    res.status(500).json({ ok: false, error: String(err) });
  }
});

/** POST /api/tasks/:id/pause - Pause a scheduled task */
app.post('/api/tasks/:id/pause', (req, res) => {
  try {
    pauseScheduledTask(req.params.id);
    res.json({ ok: true });
  } catch (err) {
    res.status(500).json({ ok: false, error: String(err) });
  }
});

/** POST /api/tasks/:id/resume - Resume a paused task */
app.post('/api/tasks/:id/resume', (req, res) => {
  try {
    resumeScheduledTask(req.params.id);
    res.json({ ok: true });
  } catch (err) {
    res.status(500).json({ ok: false, error: String(err) });
  }
});

/** DELETE /api/tasks/:id - Delete a scheduled task */
app.delete('/api/tasks/:id', (req, res) => {
  try {
    deleteScheduledTask(req.params.id);
    res.json({ ok: true });
  } catch (err) {
    res.status(500).json({ ok: false, error: String(err) });
  }
});

// ── Hive Mind API ───────────────────────────────────────────────────

/** GET /api/hive-mind - Activity feed across all agents */
app.get('/api/hive-mind', (req, res) => {
  try {
    const worker = req.query.worker as string | undefined;
    const limit = parseInt(req.query.limit as string || '30', 10);
    const entries = getHiveMindEntries(limit, worker || undefined);
    res.json({ ok: true, entries });
  } catch (err) {
    res.status(500).json({ ok: false, error: String(err) });
  }
});

// ── Static file serving (dashboard) ─────────────────────────────────

app.use(express.static(DASHBOARD_DIR));

// Fallback to index.html for unmatched routes
app.use((_req, res) => {
  res.sendFile(path.join(DASHBOARD_DIR, 'index.html'));
});

// ── Report regeneration ─────────────────────────────────────────────

function regenerateReport(): void {
  const script = path.join(DASHBOARD_DIR, 'generate_report.py');
  exec(`python3 "${script}"`, { cwd: DASHBOARD_DIR }, (err) => {
    if (err) {
      console.error('[api-server] Report regeneration failed:', err.message);
    }
  });
}

// ── Start ────────────────────────────────────────────────────────────

app.listen(PORT, '0.0.0.0', () => {
  console.log(`[api-server] Dashboard + API on http://0.0.0.0:${PORT}`);
});
