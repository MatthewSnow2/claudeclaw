#!/usr/bin/env python3
"""
EAC Command Center Report Generator (v3)
Produces structured JSON from live system state for the 4-tab dashboard.
Called by scheduled tasks (morning 0800, evening 1600) or cron (every 5 min).

Usage:
  python3 generate_report.py              # Generates report + updates latest.json
  python3 generate_report.py --type morning
  python3 generate_report.py --type evening
"""

import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

PROJECTS_DIR = Path("/home/apexaipc/projects")
DASHBOARD_DIR = Path(__file__).parent
REPORTS_DIR = DASHBOARD_DIR / "reports"
PIPELINE_FILE = PROJECTS_DIR / "claudeclaw" / "PIPELINE.md"
TIMELINE_FILE = REPORTS_DIR / "timeline.json"
ST_FACTORY_DIR = PROJECTS_DIR / "st-factory" / "data"
ST_FACTORY_RECS = ST_FACTORY_DIR / "improvement_recommendations.jsonl"
ST_FACTORY_PATCHES = ST_FACTORY_DIR / "persona_patches.jsonl"
ST_FACTORY_SIGNALS = ST_FACTORY_DIR / "research_signals.jsonl"
METROPLEX_DB = PROJECTS_DIR / "metroplex" / "data" / "metroplex.db"
CLAUDECLAW_DB = PROJECTS_DIR / "claudeclaw" / "store" / "claudeclaw.db"
IDEAFORGE_DB = PROJECTS_DIR / "ideaforge" / "data" / "ideaforge.db"
PERSONA_METRICS_DB = ST_FACTORY_DIR / "persona_metrics.db"
STARSCREAM_DB = PROJECTS_DIR / "claudeclaw" / "store" / "starscream_analytics.db"

# PM2 process name to agent identity mapping
PM2_TO_AGENT = {
    "ea-claude": {"agent_id": "data", "role": "Coordinator"},
    "ea-claude-default": {"agent_id": "redshirt", "role": "General Worker"},
    "ea-claude-starscream": {"agent_id": "starscream", "role": "Social Media"},
    "ea-claude-ravage": {"agent_id": "ravage", "role": "Coding"},
    "ea-claude-soundwave": {"agent_id": "soundwave", "role": "Research & Analysis"},
    "ea-claude-astrotrain": {"agent_id": "astrotrain", "role": "DSP/SCM Simulation"},
}

# Projects to check for git status
GIT_PROJECTS = [
    "claudeclaw", "ultra-magnus", "yce-harness", "metroplex",
    "ideaforge", "research-agents", "st-factory", "perceptor",
    "sky-lynx", "gen-ui-dashboard",
]

# Services to health-check
SERVICES = {
    "EA-Claude (Data)": {"check": "pm2", "name": "ea-claude"},
    "Metroplex": {"check": "process", "pattern": "metroplex.py"},
    "HTTP Server": {"check": "port", "port": 8080},
}


def run(cmd, timeout=10):
    """Run a shell command, return stdout or empty string on failure."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip()
    except Exception:
        return ""


def query_external_db(db_path, query_fn):
    """Safely query an external database. Returns None if unavailable."""
    if not Path(db_path).exists():
        return None
    try:
        db = sqlite3.connect(str(db_path), timeout=5)
        db.row_factory = sqlite3.Row
        result = query_fn(db)
        db.close()
        return result
    except Exception as e:
        return {"error": str(e)}


# ============================================================================
# Tab 1: Agent Overview
# ============================================================================

def get_agent_data():
    """Gather agent topology data for Tab 1."""
    result = {
        "pm2_processes": [],
        "queue_stats": {},
        "metroplex": None,
        "scheduled_tasks": [],
        "st_metro_pipeline": {},
    }

    # --- PM2 Process Status ---
    pm2_out = run("pm2 jlist 2>/dev/null")
    if pm2_out:
        try:
            for proc in json.loads(pm2_out):
                name = proc.get("name", "")
                if name in PM2_TO_AGENT:
                    pm2_env = proc.get("pm2_env", {})
                    monit = proc.get("monit", {})
                    result["pm2_processes"].append({
                        "name": name,
                        "agent_id": PM2_TO_AGENT[name]["agent_id"],
                        "role": PM2_TO_AGENT[name]["role"],
                        "status": pm2_env.get("status", "unknown"),
                        "uptime_seconds": int((time.time() * 1000 - pm2_env.get("pm_uptime", 0)) / 1000) if pm2_env.get("pm_uptime") else 0,
                        "restarts": pm2_env.get("restart_time", 0),
                        "memory_mb": round(monit.get("memory", 0) / 1024 / 1024, 1),
                    })
        except json.JSONDecodeError:
            pass

    # --- Dispatch Queue Stats (per worker_type) ---
    if CLAUDECLAW_DB.exists():
        try:
            db = sqlite3.connect(str(CLAUDECLAW_DB), timeout=5)
            now_epoch = int(time.time())
            day_ago = now_epoch - 86400

            for wtype in ["default", "starscream", "ravage", "soundwave", "astrotrain"]:
                queued = db.execute(
                    "SELECT COUNT(*) FROM dispatch_queue WHERE worker_type=? AND status='queued'", (wtype,)
                ).fetchone()[0]
                running = db.execute(
                    "SELECT COUNT(*) FROM dispatch_queue WHERE worker_type=? AND status='running'", (wtype,)
                ).fetchone()[0]
                completed_24h = db.execute(
                    "SELECT COUNT(*) FROM dispatch_queue WHERE worker_type=? AND status='completed' AND completed_at>?",
                    (wtype, day_ago)
                ).fetchone()[0]
                failed_24h = db.execute(
                    "SELECT COUNT(*) FROM dispatch_queue WHERE worker_type=? AND status='failed' AND completed_at>?",
                    (wtype, day_ago)
                ).fetchone()[0]
                last_completed = db.execute(
                    "SELECT MAX(completed_at) FROM dispatch_queue WHERE worker_type=? AND status='completed'", (wtype,)
                ).fetchone()[0]
                avg_duration = db.execute(
                    "SELECT AVG(completed_at - started_at) FROM dispatch_queue WHERE worker_type=? AND status='completed' AND started_at IS NOT NULL AND completed_at IS NOT NULL",
                    (wtype,)
                ).fetchone()[0]

                total_completed = db.execute(
                    "SELECT COUNT(*) FROM dispatch_queue WHERE worker_type=? AND status='completed'", (wtype,)
                ).fetchone()[0]
                total_failed = db.execute(
                    "SELECT COUNT(*) FROM dispatch_queue WHERE worker_type=? AND status='failed'", (wtype,)
                ).fetchone()[0]

                result["queue_stats"][wtype] = {
                    "queued": queued,
                    "running": running,
                    "completed_24h": completed_24h,
                    "failed_24h": failed_24h,
                    "last_completed_at": last_completed,
                    "avg_duration_seconds": round(avg_duration) if avg_duration else None,
                    "total_completed": total_completed,
                    "total_failed": total_failed,
                }

            # --- Scheduled Tasks ---
            tasks = db.execute("SELECT id, prompt, schedule, status, next_run FROM scheduled_tasks").fetchall()
            for t in tasks:
                result["scheduled_tasks"].append({
                    "id": t[0],
                    "prompt_preview": t[1][:60] + ("..." if len(t[1]) > 60 else ""),
                    "schedule": t[2],
                    "status": t[3],
                    "next_run": t[4],
                })

            db.close()
        except Exception:
            pass

    # --- Metroplex Data (cross-DB, guarded) ---
    result["metroplex"] = get_metroplex_status()

    # --- ST Metro Pipeline Health ---
    result["st_metro_pipeline"] = get_pipeline_health()

    # --- Tier 2: Scheduled Infrastructure (cron + systemd) ---
    result["tier2_scheduled"] = get_tier2_data()

    # --- Tier 3: On-Demand & Pipeline Components ---
    result["tier3_components"] = get_tier3_data()

    return result


def get_tier2_data():
    """Gather Tier 2 infrastructure data: systemd services and cron jobs."""
    result = {"services": [], "cron_jobs": []}

    # --- Systemd Services ---
    for svc_name, label in [("metroplex", "Metroplex")]:
        # Check user-level systemd first, fall back to system-level
        active = run(f"systemctl --user is-active {svc_name} 2>/dev/null") == "active"
        if not active:
            active = run(f"systemctl is-active {svc_name} 2>/dev/null") == "active"
        enabled = run(f"systemctl --user is-enabled {svc_name} 2>/dev/null") == "enabled"
        if not enabled:
            enabled = run(f"systemctl is-enabled {svc_name} 2>/dev/null") == "enabled"
        result["services"].append({
            "name": label,
            "service": svc_name,
            "active": active,
            "enabled": enabled,
        })

    # --- Cron Jobs ---
    cron_out = run("crontab -l 2>/dev/null")
    cron_defs = {
        "sky-lynx": {"label": "Sky-Lynx Analyzer", "role": "Weekly self-improvement"},
        "generate_report": {"label": "Dashboard Reporter", "role": "Report generation"},
        "extract_memories": {"label": "Memory Extraction", "role": "Semantic memory pipeline"},
        "watchdog": {"label": "Watchdog", "role": "Service health monitor"},
        "send_report.*morning": {"label": "Morning Report", "role": "0800 daily briefing"},
        "send_report.*evening": {"label": "Evening Report", "role": "1600 daily review"},
        "starscream_analytics": {"label": "Starscream Analytics", "role": "LinkedIn analytics"},
        "inbox_triage": {"label": "Inbox Triage", "role": "Message prioritization"},
        "retrospective": {"label": "Weekly Retrospective", "role": "Sunday review cycle"},
        "research-agents": {"label": "Research Agents", "role": "Market signal collection"},
        "updater.sh": {"label": "NVIDIA SDK Updater", "role": "Driver updates"},
    }
    for line in cron_out.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 5)
        if len(parts) < 6:
            continue
        schedule = " ".join(parts[:5])
        command = parts[5]
        matched = False
        for pattern, info in cron_defs.items():
            if re.search(pattern, command):
                result["cron_jobs"].append({
                    "label": info["label"],
                    "role": info["role"],
                    "schedule": schedule,
                    "active": True,
                })
                matched = True
                break
        if not matched:
            # Unknown cron job -- include with truncated command
            result["cron_jobs"].append({
                "label": os.path.basename(command.split()[0]) if command else "Unknown",
                "role": command[:60],
                "schedule": schedule,
                "active": True,
            })

    # --- System cron.d files (e.g. research-agents) ---
    # Format: schedule(5) username command
    crond_defs = {
        "arxiv tool-monitor": {"label": "Research: Arxiv + Tools", "role": "Daily arxiv & tool-monitor scan"},
        "domain-watch": {"label": "Research: Domain Watch", "role": "Domain signal collection (every 3 days)"},
        "idea-surfacer": {"label": "Research: Idea Surfacer", "role": "Weekly idea synthesis (Sat before Sky-Lynx)"},
    }
    crond_file = Path("/etc/cron.d/research-agents")
    if crond_file.exists():
        try:
            crond_out = crond_file.read_text()
            for line in crond_out.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                # cron.d format: min hour dom mon dow user command
                parts = line.split(None, 6)
                if len(parts) < 7:
                    continue
                schedule = " ".join(parts[:5])
                command = parts[6]  # skip parts[5] (username)
                matched = False
                for pattern, info in crond_defs.items():
                    if pattern in command:
                        result["cron_jobs"].append({
                            "label": info["label"],
                            "role": info["role"],
                            "schedule": schedule,
                            "active": True,
                            "source": "cron.d",
                        })
                        matched = True
                        break
                if not matched:
                    result["cron_jobs"].append({
                        "label": "Research: " + os.path.basename(command.split()[0]),
                        "role": command[:60],
                        "schedule": schedule,
                        "active": True,
                        "source": "cron.d",
                    })
        except PermissionError:
            pass  # Can't read cron.d file, skip

    return result


def get_tier3_data():
    """Gather Tier 3 on-demand component data: install status, DB health, last activity."""
    components = []

    tier3_defs = [
        {
            "name": "YCE Harness",
            "role": "Autonomous AI build engine",
            "path": PROJECTS_DIR / "yce-harness",
            "check": "venv",
            "venv_path": "venv/bin/python",
        },
        {
            "name": "IdeaForge",
            "role": "Market signal intake pipeline",
            "path": PROJECTS_DIR / "ideaforge",
            "check": "db",
            "db_path": str(IDEAFORGE_DB),
            "count_query": "SELECT COUNT(*) FROM ideas",
            "last_activity_query": "SELECT MAX(COALESCE(scored_at, synthesized_at, classified_at)) FROM ideas",
        },
        {
            "name": "ST Factory",
            "role": "Persona metrics & contract store",
            "path": PROJECTS_DIR / "st-factory",
            "check": "db",
            "db_path": str(PERSONA_METRICS_DB),
            "count_query": "SELECT COUNT(*) FROM outcome_records",
            "last_activity_query": "SELECT MAX(emitted_at) FROM outcome_records",
        },
        {
            "name": "Perceptor",
            "role": "Cross-session context MCP server",
            "path": PROJECTS_DIR / "perceptor",
            "check": "built",
            "built_path": "mcp-server/dist/index.js",
        },
        {
            "name": "Research Agents",
            "role": "Multi-LLM signal fleet",
            "path": PROJECTS_DIR / "research-agents",
            "check": "venv",
            "venv_path": ".venv/bin/python",
        },
        {
            "name": "Ultra-Magnus",
            "role": "Idea-to-project pipeline",
            "path": PROJECTS_DIR / "ultra-magnus",
            "check": "venv",
            "venv_path": "idea-factory/.venv/bin/python",
        },
    ]

    for comp in tier3_defs:
        entry = {
            "name": comp["name"],
            "role": comp["role"],
            "installed": comp["path"].exists(),
            "status": "unknown",
            "detail": None,
            "last_activity": None,
        }

        if not entry["installed"]:
            entry["status"] = "missing"
            components.append(entry)
            continue

        check = comp.get("check")
        if check == "venv":
            venv_exists = (comp["path"] / comp["venv_path"]).exists()
            entry["status"] = "ready" if venv_exists else "needs_setup"
            entry["detail"] = "venv OK" if venv_exists else "venv missing"
        elif check == "built":
            built = (comp["path"] / comp["built_path"]).exists()
            entry["status"] = "ready" if built else "needs_build"
            entry["detail"] = "built" if built else "needs npm run build"
        elif check == "db":
            db_path = comp.get("db_path")
            if db_path and Path(db_path).exists():
                try:
                    db = sqlite3.connect(db_path, timeout=5)
                    count = db.execute(comp["count_query"]).fetchone()[0]
                    entry["status"] = "active" if count > 0 else "empty"
                    entry["detail"] = f"{count} records"

                    last = db.execute(comp["last_activity_query"]).fetchone()[0]
                    entry["last_activity"] = last
                    db.close()
                except Exception as e:
                    entry["status"] = "error"
                    entry["detail"] = str(e)[:80]
            else:
                entry["status"] = "no_db"
                entry["detail"] = "database file missing"

        # Git last commit date as fallback activity indicator
        if not entry["last_activity"]:
            git_date = run(f"git -C {comp['path']} log -1 --format=%ct 2>/dev/null")
            if git_date and git_date.isdigit():
                entry["last_activity"] = int(git_date)

        components.append(entry)

    return components


def get_metroplex_status():
    """Query Metroplex DB for orchestrator status. Guarded -- returns None if DB missing."""
    if not METROPLEX_DB.exists():
        return None

    try:
        db = sqlite3.connect(str(METROPLEX_DB), timeout=5)
        db.row_factory = sqlite3.Row

        # Process running check
        pids = run("pgrep -f 'metroplex.py' 2>/dev/null")
        process_running = bool(pids.strip())

        # Gate status
        gates = {}
        try:
            for row in db.execute("SELECT gate, consecutive_failures, halted, last_error FROM gate_status").fetchall():
                gates[row["gate"]] = {
                    "halted": bool(row["halted"]),
                    "consecutive_failures": row["consecutive_failures"],
                    "last_error": row["last_error"],
                }
        except Exception:
            pass

        # Priority queue counts
        pq = {}
        try:
            for row in db.execute(
                "SELECT status, COUNT(*) as cnt FROM priority_queue GROUP BY status"
            ).fetchall():
                pq[row["status"]] = row["cnt"]
        except Exception:
            pass

        # Last cycle
        last_cycle = None
        total_cycles = 0
        try:
            last_cycle_row = db.execute(
                "SELECT completed_at FROM cycles WHERE completed_at IS NOT NULL ORDER BY completed_at DESC LIMIT 1"
            ).fetchone()
            last_cycle = last_cycle_row["completed_at"] if last_cycle_row else None
            total_cycles = db.execute("SELECT COUNT(*) FROM cycles").fetchone()[0]
        except Exception:
            pass

        db.close()

        return {
            "process_running": process_running,
            "gates": gates,
            "priority_queue": {
                "pending": pq.get("pending", 0),
                "dispatched": pq.get("dispatched", 0),
                "completed": pq.get("completed", 0),
                "failed": pq.get("failed", 0),
            },
            "last_cycle": last_cycle,
            "total_cycles": total_cycles,
        }
    except Exception as e:
        return {"error": str(e)}


def get_pipeline_health():
    """Assess ST Metro pipeline health across all stages."""
    result = {
        "research_agents_cron": False,
        "last_signal_age_hours": None,
        "last_idea_age_hours": None,
        "last_triage_age_hours": None,
        "pipeline_health": "unknown",
    }

    # Check cron
    cron_out = run("crontab -l 2>/dev/null")
    result["research_agents_cron"] = "research" in cron_out.lower()

    # Last research signal age (from ST Factory persona_metrics.db)
    if PERSONA_METRICS_DB.exists():
        try:
            db = sqlite3.connect(str(PERSONA_METRICS_DB), timeout=5)
            row = db.execute("SELECT MAX(emitted_at) FROM research_signals").fetchone()
            if row and row[0]:
                dt = datetime.fromisoformat(str(row[0]))
                result["last_signal_age_hours"] = round((datetime.now() - dt).total_seconds() / 3600, 1)
            db.close()
        except Exception:
            pass

    # Last idea age (from IdeaForge)
    if IDEAFORGE_DB.exists():
        try:
            db = sqlite3.connect(str(IDEAFORGE_DB), timeout=5)
            row = db.execute("SELECT MAX(created_at) FROM ideas").fetchone()
            if row and row[0]:
                try:
                    dt = datetime.fromisoformat(str(row[0]))
                except ValueError:
                    dt = datetime.fromtimestamp(int(row[0]))
                result["last_idea_age_hours"] = round((datetime.now() - dt).total_seconds() / 3600, 1)
            db.close()
        except Exception:
            pass

    # Last triage age (from Metroplex)
    if METROPLEX_DB.exists():
        try:
            db = sqlite3.connect(str(METROPLEX_DB), timeout=5)
            row = db.execute("SELECT MAX(decided_at) FROM triage_decisions").fetchone()
            if row and row[0]:
                dt = datetime.fromisoformat(str(row[0]))
                result["last_triage_age_hours"] = round((datetime.now() - dt).total_seconds() / 3600, 1)
            db.close()
        except Exception:
            pass

    # Determine overall pipeline health
    signal_fresh = result["last_signal_age_hours"] is not None and result["last_signal_age_hours"] < 48
    idea_fresh = result["last_idea_age_hours"] is not None and result["last_idea_age_hours"] < 72
    triage_fresh = result["last_triage_age_hours"] is not None and result["last_triage_age_hours"] < 96

    if signal_fresh and idea_fresh and triage_fresh:
        result["pipeline_health"] = "healthy"
    elif signal_fresh or idea_fresh:
        result["pipeline_health"] = "degraded"
    else:
        result["pipeline_health"] = "stale"

    return result


# ============================================================================
# Tab 3: HLL (Human Learning Loop)
# ============================================================================

def get_hll_data():
    """Gather Human Learning Loop data for Tab 3."""
    result = {
        "memory_stats": {},
        "extraction": {},
        "decisions": [],
        "soundwave_outputs": [],
        "learning_queue": [],
        "session_stats": {},
        "recent_memories": [],
    }

    if not CLAUDECLAW_DB.exists():
        return result

    try:
        db = sqlite3.connect(str(CLAUDECLAW_DB), timeout=5)
        now_epoch = int(time.time())
        today_start = now_epoch - (now_epoch % 86400)

        # --- Memory Stats ---
        semantic = db.execute("SELECT COUNT(*) FROM memories WHERE sector='semantic'").fetchone()[0]
        episodic = db.execute("SELECT COUNT(*) FROM memories WHERE sector='episodic'").fetchone()[0]
        vectors = db.execute("SELECT COUNT(*) FROM memory_vectors").fetchone()[0]
        semantic_today = db.execute(
            "SELECT COUNT(*) FROM memories WHERE sector='semantic' AND created_at>?", (today_start,)
        ).fetchone()[0]
        episodic_today = db.execute(
            "SELECT COUNT(*) FROM memories WHERE sector='episodic' AND created_at>?", (today_start,)
        ).fetchone()[0]

        result["memory_stats"] = {
            "semantic_count": semantic,
            "episodic_count": episodic,
            "vector_count": vectors,
            "semantic_today": semantic_today,
            "episodic_today": episodic_today,
            "total_memories": semantic + episodic,
        }

        # --- Extraction Pipeline ---
        ext = db.execute("SELECT last_log_id, last_run_at, facts_total FROM extraction_state LIMIT 1").fetchone()
        total_logs = db.execute("SELECT COUNT(*) FROM conversation_log").fetchone()[0]

        if ext:
            coverage = round((ext[0] / total_logs * 100), 1) if total_logs > 0 else 0
            result["extraction"] = {
                "last_log_id": ext[0],
                "total_log_entries": total_logs,
                "facts_total": ext[2],
                "last_run_at": ext[1],
                "coverage_pct": coverage,
            }
        else:
            result["extraction"] = {
                "last_log_id": 0,
                "total_log_entries": total_logs,
                "facts_total": 0,
                "last_run_at": None,
                "coverage_pct": 0,
            }

        # --- Decisions (extracted from conversation_log) ---
        decision_rows = db.execute("""
            SELECT id, role, substr(content, 1, 200), created_at
            FROM conversation_log
            WHERE role='assistant'
            AND (
                content LIKE '%decided%' OR content LIKE '%shelved%' OR
                content LIKE '%confirmed%' OR content LIKE '%going with%' OR
                content LIKE '%proceeding with%' OR content LIKE '%approved%' OR
                content LIKE '%rejected%' OR content LIKE '%will not%' OR
                content LIKE '%instead of%'
            )
            ORDER BY created_at DESC
            LIMIT 20
        """).fetchall()

        for row in decision_rows:
            result["decisions"].append({
                "id": row[0],
                "content": row[2],
                "status": "confirmed",
                "source_log_id": row[0],
                "source_role": row[1],
                "decided_at": row[3],
            })

        # --- Soundwave Outputs ---
        sw_rows = db.execute("""
            SELECT id, substr(prompt, 1, 100), status, substr(result, 1, 200),
                   created_at, started_at, completed_at
            FROM dispatch_queue
            WHERE worker_type='soundwave'
            ORDER BY created_at DESC
            LIMIT 10
        """).fetchall()

        for row in sw_rows:
            duration = None
            if row[5] and row[6]:
                duration = row[6] - row[5]
            result["soundwave_outputs"].append({
                "dispatch_id": row[0],
                "prompt_preview": row[1],
                "status": row[2],
                "result_preview": row[3],
                "duration_seconds": duration,
                "completed_at": row[6],
            })

        # --- Session Stats (last 7 days) ---
        week_ago = now_epoch - (7 * 86400)
        sess_row = db.execute("""
            SELECT COUNT(DISTINCT session_id) as sessions,
                   COUNT(*) as turns,
                   SUM(cost_usd) as total_cost,
                   SUM(did_compact) as compactions
            FROM token_usage
            WHERE created_at > ?
        """, (week_ago,)).fetchone()
        if sess_row:
            result["session_stats"] = {
                "sessions_7d": sess_row[0] or 0,
                "turns_7d": sess_row[1] or 0,
                "cost_7d": round(sess_row[2] or 0, 4),
                "compactions_7d": sess_row[3] or 0,
            }

        # --- Recent Memories ---
        mem_rows = db.execute("""
            SELECT id, sector, substr(content, 1, 150), salience, accessed_at
            FROM memories
            ORDER BY accessed_at DESC
            LIMIT 10
        """).fetchall()
        for row in mem_rows:
            result["recent_memories"].append({
                "id": row[0],
                "sector": row[1],
                "content_preview": row[2],
                "salience": round(row[3], 2),
                "accessed_at": row[4],
            })

        db.close()
    except Exception:
        pass

    # --- Learning Queue (from ST Factory research signals) ---
    if PERSONA_METRICS_DB.exists():
        try:
            st_db = sqlite3.connect(str(PERSONA_METRICS_DB), timeout=5)
            signals = st_db.execute("""
                SELECT title, source, summary, emitted_at, raw_json
                FROM research_signals
                WHERE relevance IN ('high', 'medium')
                ORDER BY emitted_at DESC
                LIMIT 10
            """).fetchall()

            for sig in signals:
                raw = {}
                try:
                    raw = json.loads(sig[4]) if sig[4] else {}
                except Exception:
                    pass
                result["learning_queue"].append({
                    "title": sig[0],
                    "source": sig[1],
                    "summary": (sig[2] or "")[:200],
                    "surfaced_at": sig[3][:10] if sig[3] else None,
                    "quality_score": raw.get("quality_score"),
                })

            st_db.close()
        except Exception:
            pass

    return result


# ============================================================================
# Sky-Lynx HIL (injected into Tab 3 HLL data)
# ============================================================================

SKY_LYNX_STATE = Path.home() / ".sky-lynx"
SKY_LYNX_REPORTS = Path.home() / "documentation" / "improvements"


def get_sky_lynx_hil_data():
    """Check Sky-Lynx recommendations for pending human review items."""
    result = {
        "has_pending": False,
        "pending_count": 0,
        "auto_applied_count": 0,
        "total_recs": 0,
        "budget_remaining": 3,
        "last_analysis": None,
        "report_date": None,
    }

    # Find latest recommendations sidecar
    try:
        rec_files = sorted(SKY_LYNX_REPORTS.glob("*-sky-lynx-recommendations.json"))
    except Exception:
        rec_files = []

    if not rec_files:
        return result

    latest_rec = rec_files[-1]
    result["report_date"] = latest_rec.name[:10]  # YYYY-MM-DD prefix

    try:
        recs = json.loads(latest_rec.read_text())
        if not isinstance(recs, list):
            return result
        result["total_recs"] = len(recs)

        # Extract session_id from recommendations
        session_ids = {r.get("session_id") for r in recs if r.get("session_id")}
    except Exception:
        return result

    # Read audit trail for auto-applied count
    audit_file = SKY_LYNX_STATE / "audit.jsonl"
    applied_count = 0
    if audit_file.exists():
        try:
            for line in audit_file.read_text().strip().splitlines():
                entry = json.loads(line)
                if entry.get("applied") and entry.get("session_id") in session_ids:
                    applied_count += 1
            result["last_analysis"] = entry.get("timestamp")
        except Exception:
            pass

    result["auto_applied_count"] = applied_count

    # Read cooldown state for budget
    cooldown_file = SKY_LYNX_STATE / "cooldown.json"
    if cooldown_file.exists():
        try:
            cooldown = json.loads(cooldown_file.read_text())
            used = cooldown.get("applies_this_week", 0)
            limit = cooldown.get("weekly_limit", 3)
            result["budget_remaining"] = max(0, limit - used)
        except Exception:
            pass

    # Compute pending
    result["pending_count"] = max(0, result["total_recs"] - applied_count)
    result["has_pending"] = result["pending_count"] > 0

    return result


# ============================================================================
# ============================================================================
# Tab 5: Pipeline
# ============================================================================

def get_pipeline_data():
    """Gather pipeline items and decisions for Tab 5."""
    result = {
        "stats": {"active": 0, "queued": 0, "research": 0, "shelved": 0, "killed": 0, "completed": 0},
        "items": [],
        "recent_decisions": [],
        "effort_total": 0,
        "effort_queued": 0,
        "deadline_items": [],
    }

    if not CLAUDECLAW_DB.exists():
        return result

    try:
        db = sqlite3.connect(str(CLAUDECLAW_DB), timeout=5)

        # Check table exists
        table_check = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='pipeline_items'"
        ).fetchone()
        if not table_check:
            db.close()
            return result

        # Stats by status
        for row in db.execute(
            "SELECT status, COUNT(*) as cnt FROM pipeline_items GROUP BY status"
        ).fetchall():
            if row[0] in result["stats"]:
                result["stats"][row[0]] = row[1]

        # All non-completed items (active, queued, research, shelved, killed)
        items = db.execute("""
            SELECT id, title, description, status, tier, worker_type, source,
                   effort_hours, deadline, depends_on, created_at, updated_at,
                   shelved_reason, resume_trigger
            FROM pipeline_items
            WHERE status != 'completed'
            ORDER BY
                CASE status
                    WHEN 'active' THEN 1
                    WHEN 'queued' THEN 2
                    WHEN 'research' THEN 3
                    WHEN 'shelved' THEN 4
                    WHEN 'killed' THEN 5
                END,
                CASE tier
                    WHEN 'p1' THEN 1
                    WHEN 'p2' THEN 2
                    WHEN 'p3' THEN 3
                    WHEN 'parked' THEN 4
                END,
                updated_at DESC
        """).fetchall()

        for row in items:
            result["items"].append({
                "id": row[0],
                "title": row[1],
                "description": row[2],
                "status": row[3],
                "tier": row[4],
                "worker_type": row[5],
                "source": row[6],
                "effort_hours": row[7],
                "deadline": row[8],
                "depends_on": row[9],
                "created_at": row[10],
                "updated_at": row[11],
                "shelved_reason": row[12],
                "resume_trigger": row[13],
            })

        # Effort totals
        effort_row = db.execute(
            "SELECT COALESCE(SUM(effort_hours), 0) FROM pipeline_items WHERE status IN ('active', 'queued', 'research')"
        ).fetchone()
        result["effort_total"] = effort_row[0] if effort_row else 0

        effort_q = db.execute(
            "SELECT COALESCE(SUM(effort_hours), 0) FROM pipeline_items WHERE status = 'queued'"
        ).fetchone()
        result["effort_queued"] = effort_q[0] if effort_q else 0

        # Items with deadlines
        deadline_items = db.execute(
            "SELECT title, deadline, status FROM pipeline_items WHERE deadline IS NOT NULL AND status NOT IN ('completed', 'killed') ORDER BY deadline"
        ).fetchall()
        for d in deadline_items:
            result["deadline_items"].append({
                "title": d[0], "deadline": d[1], "status": d[2]
            })

        # Recent decisions (last 20)
        decisions = db.execute("""
            SELECT d.decision, d.reason, d.decided_by, d.created_at, p.title
            FROM pipeline_decisions d
            LEFT JOIN pipeline_items p ON d.pipeline_item_id = p.id
            ORDER BY d.created_at DESC
            LIMIT 20
        """).fetchall()
        for dec in decisions:
            result["recent_decisions"].append({
                "decision": dec[0],
                "reason": dec[1],
                "decided_by": dec[2],
                "created_at": dec[3],
                "item_title": dec[4],
            })

        db.close()
    except Exception:
        pass

    return result


# Tab 4: Strategy (Christensen Filter)
# ============================================================================

def get_christensen_data():
    """Gather Christensen filter evaluation data for Tab 4."""
    result = {
        "stats": {"total": 0, "passed": 0, "failed": 0, "overridden": 0},
        "evaluations": [],
        "recent_ideas_pipeline": [],
    }

    if CLAUDECLAW_DB.exists():
        try:
            db = sqlite3.connect(str(CLAUDECLAW_DB), timeout=5)

            # Check if christensen_log table exists
            table_check = db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='christensen_log'"
            ).fetchone()

            if table_check:
                # --- Stats ---
                stats_row = db.execute("""
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN outcome='pass' THEN 1 ELSE 0 END) as passed,
                        SUM(CASE WHEN outcome='fail' THEN 1 ELSE 0 END) as failed,
                        SUM(CASE WHEN outcome='override' THEN 1 ELSE 0 END) as overridden
                    FROM christensen_log
                """).fetchone()
                if stats_row:
                    result["stats"] = {
                        "total": stats_row[0] or 0,
                        "passed": stats_row[1] or 0,
                        "failed": stats_row[2] or 0,
                        "overridden": stats_row[3] or 0,
                    }

                # --- Recent Evaluations ---
                eval_rows = db.execute("""
                    SELECT id, idea, job_to_do, serves_m2ai, beachhead, outcome, reasoning, source, created_at
                    FROM christensen_log
                    ORDER BY created_at DESC
                    LIMIT 20
                """).fetchall()

                for row in eval_rows:
                    result["evaluations"].append({
                        "id": row[0],
                        "idea": row[1],
                        "job_to_do": row[2],
                        "serves_m2ai": row[3],
                        "beachhead": row[4],
                        "outcome": row[5],
                        "reasoning": row[6],
                        "source": row[7],
                        "created_at": row[8],
                    })
            else:
                # Table doesn't exist yet -- fall back to conversation_log heuristic
                filter_rows = db.execute("""
                    SELECT id, substr(content, 1, 300), created_at
                    FROM conversation_log
                    WHERE role='assistant'
                    AND (
                        content LIKE '%Christensen filter%' OR
                        content LIKE '%christensen filter%' OR
                        content LIKE '%doesn''t pass the%filter%' OR
                        content LIKE '%passes the%filter%' OR
                        content LIKE '%job does this hire%' OR
                        content LIKE '%beachhead or a distraction%'
                    )
                    ORDER BY created_at DESC
                    LIMIT 20
                """).fetchall()

                for row in filter_rows:
                    content = row[1]
                    outcome = "unknown"
                    if "doesn't pass" in content.lower() or "does not pass" in content.lower() or "fail" in content.lower():
                        outcome = "fail"
                    elif "passes" in content.lower() or "pass" in content.lower():
                        outcome = "pass"

                    result["evaluations"].append({
                        "id": row[0],
                        "idea": content[:100],
                        "job_to_do": None,
                        "serves_m2ai": None,
                        "beachhead": None,
                        "outcome": outcome,
                        "reasoning": content[:200],
                        "source": "conversation_heuristic",
                        "created_at": row[2],
                    })

                # Update stats from heuristic results
                result["stats"]["total"] = len(result["evaluations"])
                result["stats"]["passed"] = sum(1 for e in result["evaluations"] if e["outcome"] == "pass")
                result["stats"]["failed"] = sum(1 for e in result["evaluations"] if e["outcome"] == "fail")

            db.close()
        except Exception:
            pass

    # --- IdeaForge Pipeline (recent ideas) ---
    if IDEAFORGE_DB.exists():
        try:
            idb = sqlite3.connect(str(IDEAFORGE_DB), timeout=5)
            # Try to read ideas -- schema may vary
            try:
                idea_rows = idb.execute("""
                    SELECT id, title, COALESCE(source_signals, '') as source,
                           status, COALESCE(scored_at, synthesized_at, classified_at) as created_at,
                           weighted_score
                    FROM ideas
                    ORDER BY COALESCE(scored_at, synthesized_at, classified_at) DESC
                    LIMIT 10
                """).fetchall()
                for row in idea_rows:
                    result["recent_ideas_pipeline"].append({
                        "id": row[0],
                        "title": row[1],
                        "source": row[2][:80] if row[2] else "",
                        "status": row[3],
                        "created_at": str(row[4]) if row[4] else None,
                        "score": row[5],
                    })
            except Exception:
                # Schema might not have these columns
                pass
            idb.close()
        except Exception:
            pass

    return result


# ============================================================================
# Social Analytics (Starscream)
# ============================================================================

def get_social_analytics():
    """Query starscream_analytics.db for social media metrics. Returns structured JSON for the Strategy tab."""
    result = {
        "kpi": {
            "total_impressions_30d": 0,
            "avg_engagement_rate_30d": 0.0,
            "follower_count": 0,
            "follower_change_7d": 0,
            "post_count_30d": 0,
            "top_engagement_rate": 0.0,
        },
        "top_posts_7d": [],
        "top_posts_30d": [],
        "best_time_heatmap": [],
        "posting_frequency": {
            "current_posts_per_week": 0.0,
            "optimal_posts_per_week": 0.0,
            "correlation": 0.0,
        },
        "follower_trend": [],
        "content_decay_recent": [],
        "content_insights": [],
        "daily_trend": [],
    }

    if not STARSCREAM_DB.exists():
        return result

    try:
        db = sqlite3.connect(str(STARSCREAM_DB), timeout=5)
        db.row_factory = sqlite3.Row
    except Exception:
        return result

    now = datetime.now()
    cutoff_30d = (now - timedelta(days=30)).isoformat()
    cutoff_7d = (now - timedelta(days=7)).isoformat()

    # --- KPIs from daily_aggregate (30d) ---
    try:
        kpi_row = db.execute("""
            SELECT
                COALESCE(SUM(total_impressions), 0) as total_imp,
                COALESCE(AVG(avg_engagement_rate), 0.0) as avg_eng,
                COALESCE(SUM(total_posts), 0) as post_count
            FROM daily_aggregate
            WHERE date >= ?
        """, (cutoff_30d[:10],)).fetchone()
        if kpi_row:
            result["kpi"]["total_impressions_30d"] = kpi_row["total_imp"]
            result["kpi"]["avg_engagement_rate_30d"] = round(kpi_row["avg_eng"], 4)
            result["kpi"]["post_count_30d"] = kpi_row["post_count"]
    except Exception:
        pass

    # Follower count (latest daily_aggregate)
    try:
        fc_row = db.execute(
            "SELECT follower_count FROM daily_aggregate ORDER BY date DESC LIMIT 1"
        ).fetchone()
        if fc_row:
            result["kpi"]["follower_count"] = fc_row["follower_count"]
    except Exception:
        pass

    # Follower change over 7 days
    try:
        fc_7d = db.execute("""
            SELECT
                (SELECT total_followers FROM follower_metrics ORDER BY collected_at DESC LIMIT 1)
                -
                COALESCE(
                    (SELECT total_followers FROM follower_metrics WHERE collected_at <= ? ORDER BY collected_at DESC LIMIT 1),
                    (SELECT total_followers FROM follower_metrics ORDER BY collected_at ASC LIMIT 1)
                ) as change_7d
        """, (cutoff_7d,)).fetchone()
        if fc_7d and fc_7d["change_7d"] is not None:
            result["kpi"]["follower_change_7d"] = fc_7d["change_7d"]
    except Exception:
        pass

    # Top engagement rate (30d, from post_metrics with latest snapshot per post)
    try:
        top_eng = db.execute("""
            SELECT MAX(engagement_rate) as top_er
            FROM post_metrics
            WHERE collected_at >= ?
        """, (cutoff_30d,)).fetchone()
        if top_eng and top_eng["top_er"] is not None:
            result["kpi"]["top_engagement_rate"] = round(top_eng["top_er"], 4)
    except Exception:
        pass

    # --- Top Posts 7d (top 5 by engagement, latest snapshot per post) ---
    try:
        top7 = db.execute("""
            SELECT p.id, p.content_preview, p.published_at, p.likes, p.comments,
                   p.shares, p.impressions, p.engagement_rate
            FROM post_metrics p
            INNER JOIN (
                SELECT id, MAX(collected_at) as max_collected
                FROM post_metrics
                WHERE published_at >= ?
                GROUP BY id
            ) latest ON p.id = latest.id AND p.collected_at = latest.max_collected
            ORDER BY p.engagement_rate DESC
            LIMIT 5
        """, (cutoff_7d,)).fetchall()
        for row in top7:
            result["top_posts_7d"].append({
                "id": str(row["id"]),
                "content_preview": row["content_preview"] or "",
                "published_at": row["published_at"] or "",
                "likes": row["likes"] or 0,
                "comments": row["comments"] or 0,
                "shares": row["shares"] or 0,
                "impressions": row["impressions"] or 0,
                "engagement_rate": round(row["engagement_rate"] or 0.0, 4),
            })
    except Exception:
        pass

    # --- Top Posts 30d (top 5 by engagement, latest snapshot per post) ---
    try:
        top30 = db.execute("""
            SELECT p.id, p.content_preview, p.published_at, p.likes, p.comments,
                   p.shares, p.impressions, p.engagement_rate
            FROM post_metrics p
            INNER JOIN (
                SELECT id, MAX(collected_at) as max_collected
                FROM post_metrics
                WHERE published_at >= ?
                GROUP BY id
            ) latest ON p.id = latest.id AND p.collected_at = latest.max_collected
            ORDER BY p.engagement_rate DESC
            LIMIT 5
        """, (cutoff_30d,)).fetchall()
        for row in top30:
            result["top_posts_30d"].append({
                "id": str(row["id"]),
                "content_preview": row["content_preview"] or "",
                "published_at": row["published_at"] or "",
                "likes": row["likes"] or 0,
                "comments": row["comments"] or 0,
                "shares": row["shares"] or 0,
                "impressions": row["impressions"] or 0,
                "engagement_rate": round(row["engagement_rate"] or 0.0, 4),
            })
    except Exception:
        pass

    # --- Best Time Heatmap (from content_insights best_time entries) ---
    try:
        ci_exists = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='content_insights'"
        ).fetchone()
        if ci_exists:
            bt_rows = db.execute("""
                SELECT insight_key, insight_value, metric_value, sample_size
                FROM content_insights
                WHERE insight_type = 'best_time'
                ORDER BY generated_at DESC, metric_value DESC
            """).fetchall()
            seen_keys = set()
            for row in bt_rows:
                key = row["insight_key"]
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                try:
                    detail = json.loads(row["insight_value"])
                except Exception:
                    continue
                result["best_time_heatmap"].append({
                    "day": detail.get("day", ""),
                    "hour": detail.get("hour", 0),
                    "score": round(detail.get("avg_engagement", 0), 4),
                    "impressions": 0,
                    "engagement_rate": round(detail.get("avg_engagement", 0), 4),
                    "post_count": detail.get("post_count", 0),
                })
    except Exception:
        pass

    # --- Posting Frequency (from posting_frequency, most recent) ---
    try:
        table_exists = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='posting_frequency'"
        ).fetchone()
        if table_exists:
            pf_row = db.execute("""
                SELECT current_posts_per_week, optimal_posts_per_week, correlation
                FROM posting_frequency
                ORDER BY collected_at DESC
                LIMIT 1
            """).fetchone()
            if pf_row:
                result["posting_frequency"] = {
                    "current_posts_per_week": round(pf_row["current_posts_per_week"] or 0.0, 2),
                    "optimal_posts_per_week": round(pf_row["optimal_posts_per_week"] or 0.0, 2),
                    "correlation": round(pf_row["correlation"] or 0.0, 4),
                }
    except Exception:
        pass

    # --- Follower Trend (last 30 data points) ---
    try:
        ft_rows = db.execute("""
            SELECT collected_at, total_followers, new_followers_24h
            FROM follower_metrics
            ORDER BY collected_at DESC
            LIMIT 30
        """).fetchall()
        for row in ft_rows:
            result["follower_trend"].append({
                "date": row["collected_at"],
                "total": row["total_followers"] or 0,
                "new_24h": row["new_followers_24h"] or 0,
            })
        # Reverse so oldest is first (chronological order)
        result["follower_trend"].reverse()
    except Exception:
        pass

    # --- Content Decay Recent (last 5 posts with decay data) ---
    try:
        table_exists = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='content_decay'"
        ).fetchone()
        if table_exists:
            # Get distinct post_ids with decay data, most recent first
            decay_posts = db.execute("""
                SELECT DISTINCT cd.post_id, pm.content_preview
                FROM content_decay cd
                LEFT JOIN post_metrics pm ON cd.post_id = pm.id
                    AND pm.collected_at = (SELECT MAX(collected_at) FROM post_metrics WHERE id = cd.post_id)
                ORDER BY cd.post_id DESC
                LIMIT 5
            """).fetchall()
            for dp in decay_posts:
                post_id = dp["post_id"]
                preview = dp["content_preview"] or ""
                # Get decay points for this post
                decay_points = db.execute("""
                    SELECT hours_since_publish, cumulative_impressions, cumulative_engagement
                    FROM content_decay
                    WHERE post_id = ?
                    ORDER BY hours_since_publish ASC
                """, (post_id,)).fetchall()
                points = []
                for pt in decay_points:
                    points.append({
                        "hours": pt["hours_since_publish"] or 0,
                        "impressions": pt["cumulative_impressions"] or 0,
                        "engagement": pt["cumulative_engagement"] or 0,
                    })
                result["content_decay_recent"].append({
                    "post_id": str(post_id),
                    "content_preview": preview,
                    "decay_points": points,
                })
    except Exception:
        pass

    # --- Content Insights (from content_insights table, most recent analysis) ---
    try:
        table_exists = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='content_insights'"
        ).fetchone()
        if table_exists:
            latest_date = db.execute(
                "SELECT MAX(generated_at) as latest FROM content_insights"
            ).fetchone()
            if latest_date and latest_date["latest"]:
                # Get the date prefix for the latest analysis run
                latest_prefix = latest_date["latest"][:10]
                ci_rows = db.execute("""
                    SELECT insight_type, insight_key, insight_value, metric_value, sample_size
                    FROM content_insights
                    WHERE generated_at LIKE ?
                    ORDER BY metric_value DESC
                """, (f"{latest_prefix}%",)).fetchall()
                for row in ci_rows:
                    detail = {}
                    try:
                        detail = json.loads(row["insight_value"]) if row["insight_value"] else {}
                    except (json.JSONDecodeError, TypeError):
                        pass
                    result["content_insights"].append({
                        "insight_type": row["insight_type"] or "",
                        "metric_name": row["insight_key"] or "",
                        "metric_value": round(row["metric_value"] or 0.0, 4),
                        "detail": detail,
                        "sample_size": row["sample_size"] or 0,
                    })
    except Exception:
        pass

    # --- Daily Trend (last 30 days from daily_aggregate) ---
    try:
        dt_rows = db.execute("""
            SELECT date, total_impressions, total_likes, total_comments, avg_engagement_rate
            FROM daily_aggregate
            ORDER BY date DESC
            LIMIT 30
        """).fetchall()
        for row in dt_rows:
            result["daily_trend"].append({
                "date": row["date"],
                "impressions": row["total_impressions"] or 0,
                "likes": row["total_likes"] or 0,
                "comments": row["total_comments"] or 0,
                "engagement_rate": round(row["avg_engagement_rate"] or 0.0, 4),
            })
        # Reverse so oldest is first (chronological order)
        result["daily_trend"].reverse()
    except Exception:
        pass

    try:
        db.close()
    except Exception:
        pass

    return result


# ============================================================================
# Existing v2 functions (unchanged)
# ============================================================================

def check_service_health():
    """Check all monitored services."""
    items = []

    # PM2 processes
    pm2_out = run("pm2 jlist 2>/dev/null")
    pm2_procs = {}
    if pm2_out:
        try:
            for proc in json.loads(pm2_out):
                pm2_procs[proc.get("name", "")] = proc.get("pm2_env", {}).get("status", "unknown")
        except json.JSONDecodeError:
            pass

    # Systemd services
    def systemd_status(name):
        out = run(f"systemctl is-active {name} 2>/dev/null")
        return out.strip()

    # Port checks
    def port_open(port):
        out = run(f"lsof -i :{port} -t 2>/dev/null")
        return bool(out.strip())

    for label, cfg in SERVICES.items():
        if cfg["check"] == "pm2":
            status_str = pm2_procs.get(cfg["name"], "not found")
            if status_str == "online":
                items.append({"text": label, "detail": "Running via pm2", "status": "ok"})
            elif status_str == "not found":
                items.append({"text": label, "detail": "Not found in pm2 process list", "status": "error"})
            else:
                items.append({"text": label, "detail": f"Status: {status_str}", "status": "warning"})

        elif cfg["check"] == "process":
            pattern = cfg["pattern"]
            pids = run(f"pgrep -f '{pattern}' 2>/dev/null")
            if pids:
                pid = pids.split("\n")[0]
                items.append({"text": label, "detail": f"Running (PID {pid})", "status": "ok"})
            else:
                items.append({"text": label, "detail": "Not running", "status": "error"})

        elif cfg["check"] == "systemd":
            st = systemd_status(cfg["name"])
            if st == "active":
                items.append({"text": label, "detail": "systemd service active", "status": "ok"})
            elif st == "inactive":
                items.append({"text": label, "detail": "systemd service inactive", "status": "warning"})
            else:
                items.append({"text": label, "detail": f"systemd status: {st}", "status": "error"})

        elif cfg["check"] == "port":
            if port_open(cfg["port"]):
                items.append({"text": label, "detail": f"Listening on port {cfg['port']}", "status": "ok"})
            else:
                items.append({"text": label, "detail": f"Nothing on port {cfg['port']}", "status": "error"})

    # Cron checks
    cron_out = run("crontab -l 2>/dev/null")
    if "research" in cron_out.lower():
        items.append({"text": "Research Agents (cron)", "detail": "Cron entry found", "status": "ok"})
    else:
        items.append({"text": "Research Agents (cron)", "detail": "No cron entry found", "status": "warning"})

    if "sky-lynx" in cron_out.lower() or "sky_lynx" in cron_out.lower():
        items.append({"text": "Sky-Lynx (cron)", "detail": "Cron entry found", "status": "ok"})
    else:
        items.append({"text": "Sky-Lynx (cron)", "detail": "No cron entry found", "status": "warning"})

    return {"title": "Service Health", "items": items}


def check_pipeline():
    """Parse PIPELINE.md for active tasks and their status."""
    items = []
    if not PIPELINE_FILE.exists():
        return {"title": "Pipeline Status", "items": [{"text": "PIPELINE.md not found", "detail": "", "status": "error"}]}

    content = PIPELINE_FILE.read_text()
    lines = content.split("\n")

    current_section = ""
    for line in lines:
        stripped = line.strip()

        # Track section headers
        if stripped.startswith("## PRIORITY"):
            current_section = stripped
        elif stripped.startswith("## PARKED") or stripped.startswith("## CLOSED"):
            current_section = stripped

        # Skip closed/parked sections
        if "PARKED" in current_section or "CLOSED" in current_section:
            continue

        # Grab checkbox items
        if stripped.startswith("- [x]"):
            task = stripped[6:].strip()
            items.append({"text": task[:80], "detail": current_section, "status": "ok"})
        elif stripped.startswith("- [ ]"):
            task = stripped[6:].strip()
            items.append({"text": task[:80], "detail": current_section, "status": "warning"})

    # Pipeline view: recent completions + high-priority open items only
    open_items = [i for i in items if i["status"] != "ok"]
    recent_done = [i for i in items if i["status"] == "ok"][-3:]

    # Limit open to P1/P2 only (skip P3 detail -- that goes in Unfinished)
    p1_p2_open = [i for i in open_items if "PRIORITY 1" in i["detail"] or "PRIORITY 2" in i["detail"]]
    p3_summary = len([i for i in open_items if "PRIORITY 3" in i["detail"] or "continued" in i["detail"]])

    result_items = recent_done + p1_p2_open
    if p3_summary > 0:
        result_items.append({"text": f"{p3_summary} items in Priority 3 pipeline", "detail": "See Unfinished Business section", "status": "info"})

    return {"title": "Pipeline Status", "items": result_items}


def check_activity():
    """Check recent git activity across projects."""
    items = []
    cutoff = datetime.now() - timedelta(days=7)
    cutoff_str = cutoff.strftime("%Y-%m-%d")

    for proj in GIT_PROJECTS:
        proj_dir = PROJECTS_DIR / proj
        if not (proj_dir / ".git").exists():
            continue

        # Get last commit
        log = run(f"git -C {proj_dir} log -1 --format='%h|%s|%ar' 2>/dev/null")
        if not log:
            continue

        parts = log.split("|", 2)
        if len(parts) == 3:
            sha, msg, ago = parts
            # Count commits this week
            count = run(f"git -C {proj_dir} rev-list --count --since='{cutoff_str}' HEAD 2>/dev/null")
            count = count if count else "0"

            status = "ok" if int(count) > 0 else "info"
            items.append({
                "text": f"{proj}: {msg[:50]}",
                "detail": f"{sha} ({ago}) -- {count} commits this week",
                "status": status
            })

    items.sort(key=lambda x: x["status"] != "ok")
    return {"title": "Recent Activity", "items": items}


def check_uncommitted():
    """Check for uncommitted changes across projects."""
    items = []

    for proj in GIT_PROJECTS:
        proj_dir = PROJECTS_DIR / proj
        if not (proj_dir / ".git").exists():
            continue

        status = run(f"git -C {proj_dir} status --porcelain 2>/dev/null")
        if status:
            lines = status.strip().split("\n")
            modified = len([l for l in lines if l.startswith(" M") or l.startswith("M ")])
            untracked = len([l for l in lines if l.startswith("??")])
            staged = len([l for l in lines if l[0] in "AMDRC" and l[0] != "?"])

            parts = []
            if modified: parts.append(f"{modified} modified")
            if untracked: parts.append(f"{untracked} untracked")
            if staged: parts.append(f"{staged} staged")

            sev = "warning" if modified + staged > 0 else "info"
            items.append({
                "text": f"{proj}: {', '.join(parts)}",
                "detail": "\n".join(lines[:5]),
                "status": sev
            })

    if not items:
        items.append({"text": "All repos clean", "detail": "", "status": "ok"})

    return {"title": "Uncommitted Changes", "items": items}


def get_priorities():
    """Extract priority items from PIPELINE.md (open tasks in P1/P2)."""
    items = []
    if not PIPELINE_FILE.exists():
        return {"title": "Priorities", "items": []}

    content = PIPELINE_FILE.read_text()
    in_priority = False
    section_name = ""

    for line in content.split("\n"):
        stripped = line.strip()

        if stripped.startswith("## PRIORITY 1") or stripped.startswith("## PRIORITY 2"):
            in_priority = True
            section_name = stripped
        elif stripped.startswith("## PRIORITY 3") or stripped.startswith("## PARKED") or stripped.startswith("## CLOSED"):
            in_priority = False

        if in_priority and stripped.startswith("- [ ]"):
            task = stripped[6:].strip()
            items.append({
                "text": task[:80],
                "detail": section_name,
                "status": "warning"
            })

    return {"title": "Priorities", "items": items}


def get_unfinished():
    """Get P3 items grouped by heading (not individual checkboxes)."""
    headings = {}
    if not PIPELINE_FILE.exists():
        return {"title": "Unfinished Business", "items": []}

    content = PIPELINE_FILE.read_text()
    in_p3 = False
    current_heading = ""

    for line in content.split("\n"):
        stripped = line.strip()

        if stripped.startswith("### ") and in_p3:
            current_heading = stripped[4:].strip()
            clean = re.sub(r"\s*\(.*?\)\s*$", "", current_heading)
            if clean not in headings:
                headings[clean] = {"total": 0, "done": 0, "notes": []}

        if "PRIORITY 3" in stripped:
            in_p3 = True
        elif stripped.startswith("## PARKED") or stripped.startswith("## CLOSED"):
            in_p3 = False

        if in_p3 and current_heading:
            clean = re.sub(r"\s*\(.*?\)\s*$", "", current_heading)
            if stripped.startswith("- [ ]"):
                headings.get(clean, {}).get("total", 0)
                if clean in headings:
                    headings[clean]["total"] += 1
            elif stripped.startswith("- [x]"):
                if clean in headings:
                    headings[clean]["done"] += 1
                    headings[clean]["total"] += 1
            elif stripped.startswith("- Note:") or stripped.startswith("- **"):
                if clean in headings:
                    note = stripped.lstrip("- ").strip()
                    headings[clean]["notes"].append(note[:80])

    items = []
    for heading, data in headings.items():
        open_count = data["total"] - data["done"]
        if open_count == 0:
            continue
        progress = f"{data['done']}/{data['total']} done"
        note = data["notes"][0] if data["notes"] else ""
        items.append({
            "text": f"{heading} ({progress})",
            "detail": note,
            "status": "info" if data["done"] == 0 else "warning"
        })

    return {"title": "Unfinished Business", "items": items}


def _read_jsonl(path):
    """Read a JSONL file into a list of dicts."""
    items = []
    if not path.exists():
        return items
    for line in path.read_text().strip().split("\n"):
        if not line.strip():
            continue
        try:
            items.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return items


def get_soundwave_recommendations():
    """Read improvement recommendations from ST Factory for operator review."""
    items = []

    # --- 1. Improvement Recommendations (Sky-Lynx) ---
    recs = _read_jsonl(ST_FACTORY_RECS)
    real_recs = [r for r in recs if "[DRY RUN]" not in r.get("title", "")]

    priority_order = {"high": 0, "medium": 1, "low": 2}
    real_recs.sort(key=lambda r: (
        priority_order.get(r.get("priority", "low"), 2),
        r.get("emitted_at", "")
    ))
    real_recs.reverse()
    real_recs.sort(key=lambda r: priority_order.get(r.get("priority", "low"), 2))

    for rec in real_recs[:6]:
        priority = rec.get("priority", "medium")
        status_val = rec.get("status", "pending")
        rec_type = rec.get("recommendation_type", "other")
        change = rec.get("suggested_change", "")
        emitted = rec.get("emitted_at", "")[:10]

        if status_val == "applied":
            dot_status = "ok"
        elif priority == "high":
            dot_status = "warning"
        else:
            dot_status = "info"

        detail_parts = [f"[REC] {rec_type}"]
        if priority:
            detail_parts.append(f"Priority: {priority}")
        if emitted:
            detail_parts.append(f"From: {emitted}")
        if change:
            detail_parts.append(f"Change: {change[:80]}")

        items.append({
            "text": rec.get("title", "Untitled recommendation"),
            "detail": " | ".join(detail_parts),
            "status": dot_status
        })

    # --- 2. Metroplex Priority Queue (stuck/dispatched items) ---
    try:
        if METROPLEX_DB.exists():
            db = sqlite3.connect(str(METROPLEX_DB), timeout=5)
            db.row_factory = sqlite3.Row

            dispatched = db.execute(
                "SELECT title, source, priority_score, dispatched_at FROM priority_queue WHERE status='dispatched' ORDER BY priority_score DESC LIMIT 5"
            ).fetchall()
            for row in dispatched:
                age = ""
                if row["dispatched_at"]:
                    try:
                        dt = datetime.fromisoformat(row["dispatched_at"])
                        hours = (datetime.now() - dt).total_seconds() / 3600
                        age = f" ({hours:.0f}h ago)" if hours > 1 else " (recent)"
                    except Exception:
                        pass
                items.append({
                    "text": f"[QUEUE] {row['title'][:60]}",
                    "detail": f"Source: {row['source']} | Score: {row['priority_score']:.1f} | Dispatched{age}",
                    "status": "warning"
                })

            pending = db.execute(
                "SELECT title, source, priority_score FROM priority_queue WHERE status='pending' ORDER BY priority_score DESC LIMIT 3"
            ).fetchall()
            for row in pending:
                items.append({
                    "text": f"[QUEUE] {row['title'][:60]}",
                    "detail": f"Source: {row['source']} | Score: {row['priority_score']:.1f} | Waiting for dispatch",
                    "status": "info"
                })

            failed = db.execute(
                "SELECT title, source FROM priority_queue WHERE status='failed' ORDER BY completed_at DESC LIMIT 3"
            ).fetchall()
            for row in failed:
                items.append({
                    "text": f"[QUEUE FAILED] {row['title'][:60]}",
                    "detail": f"Source: {row['source']} | Build failed - needs review",
                    "status": "error"
                })

            db.close()
    except Exception as e:
        items.append({"text": f"Metroplex DB error: {str(e)[:50]}", "detail": "", "status": "error"})

    # --- 3. Persona Patches (pending review) ---
    patches = _read_jsonl(ST_FACTORY_PATCHES)
    pending_patches = [p for p in patches if p.get("status") in ("pending", "proposed")]
    for patch in pending_patches[:3]:
        persona = patch.get("persona_id", "unknown")
        rationale = patch.get("rationale", "")[:80]
        version = f"{patch.get('from_version', '?')} -> {patch.get('to_version', '?')}"
        ops = [p.get("operation", "?") + " " + p.get("path", "?") for p in patch.get("patches", [])]
        ops_str = ", ".join(ops[:2])
        items.append({
            "text": f"[PATCH] {persona} ({version}): {ops_str}",
            "detail": rationale,
            "status": "warning"
        })

    # --- 4. High-scoring Research Signals ---
    signals = _read_jsonl(ST_FACTORY_SIGNALS)
    cutoff = (datetime.now() - timedelta(days=7)).isoformat()
    recent_signals = [
        s for s in signals
        if s.get("quality_score", 0) > 0.7
        and s.get("ingested_at", "") > cutoff
    ]
    recent_signals.sort(key=lambda s: s.get("quality_score", 0), reverse=True)
    for sig in recent_signals[:3]:
        score = sig.get("quality_score", 0)
        source = sig.get("source_agent", "unknown")
        title = sig.get("title", sig.get("signal_type", "Signal"))[:60]
        items.append({
            "text": f"[SIGNAL] {title}",
            "detail": f"Source: {source} | Quality: {score:.2f}",
            "status": "info"
        })

    if not items:
        items.append({"text": "No actionable items", "detail": "System quiet - no recommendations, queue items, or signals needing attention", "status": "ok"})

    return {"title": "Soundwave - Operator Review", "items": items}


# ============================================================================
# Timeline + Report Generation
# ============================================================================

def count_daily_commits():
    """Count git commits made today across all tracked projects."""
    total = 0
    today_start = datetime.now().strftime("%Y-%m-%d 00:00:00")
    for project in GIT_PROJECTS:
        repo = PROJECTS_DIR / project
        if not (repo / ".git").exists():
            continue
        try:
            result = subprocess.run(
                ["git", "-C", str(repo), "log", "--oneline", f"--since={today_start}"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                lines = [l for l in result.stdout.strip().split("\n") if l]
                total += len(lines)
        except (subprocess.TimeoutExpired, OSError):
            pass
    return total


def update_timeline(completed_items):
    """Update timeline.json with today's completed count (git commits)."""
    today = datetime.now().strftime("%Y-%m-%d")
    day_name = datetime.now().strftime("%a")

    timeline = {"weekly": [], "totals": {"week": 0}}
    if TIMELINE_FILE.exists():
        try:
            timeline = json.loads(TIMELINE_FILE.read_text())
        except json.JSONDecodeError:
            pass

    found = False
    for entry in timeline.get("weekly", []):
        if entry["date"] == today:
            entry["completed"] = completed_items
            found = True
            break

    if not found:
        timeline.setdefault("weekly", []).append({
            "date": today,
            "day": day_name,
            "completed": completed_items,
            "items": []
        })

    timeline["weekly"] = timeline["weekly"][-7:]
    timeline["totals"]["week"] = sum(e["completed"] for e in timeline["weekly"])

    TIMELINE_FILE.write_text(json.dumps(timeline, indent=2))


def generate():
    """Generate full report with v3 4-tab structure."""
    report_type = "morning"
    if len(sys.argv) > 2 and sys.argv[1] == "--type":
        report_type = sys.argv[2]

    now = datetime.now()
    timestamp = now.isoformat()

    # Gather existing v2 sections (backward compat)
    service_health = check_service_health()
    pipeline = check_pipeline()
    activity = check_activity()
    uncommitted = check_uncommitted()
    priorities = get_priorities()
    unfinished = get_unfinished()
    soundwave = get_soundwave_recommendations()

    # Gather v3 tab data
    agent_data = get_agent_data()
    hll_data = get_hll_data()
    hll_data["sky_lynx_hil"] = get_sky_lynx_hil_data()
    christensen_data = get_christensen_data()
    christensen_data["social_analytics"] = get_social_analytics()
    pipeline_tab_data = get_pipeline_data()

    report = {
        "timestamp": timestamp,
        "type": report_type,

        # v2 backward compat (Tab 2 uses this directly)
        "sections": {
            "service_health": service_health,
            "pipeline": pipeline,
            "soundwave": soundwave,
            "activity": activity,
            "uncommitted": uncommitted,
            "priorities": priorities,
            "unfinished": unfinished,
        },

        # v3 tab-specific data
        "tabs": {
            "agents": agent_data,
            "operations": {
                "sections": {
                    "service_health": service_health,
                    "pipeline": pipeline,
                    "soundwave": soundwave,
                    "activity": activity,
                    "uncommitted": uncommitted,
                    "priorities": priorities,
                    "unfinished": unfinished,
                }
            },
            "hll": hll_data,
            "strategy": christensen_data,
            "pipeline_tab": pipeline_tab_data,
        }
    }

    # Count daily git commits as the productivity metric for the timeline
    daily_commits = count_daily_commits()
    update_timeline(daily_commits)

    # Write dated file
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = now.strftime("%Y-%m-%d")
    hour_str = now.strftime("%H%M")
    dated_path = REPORTS_DIR / f"{date_str}_{hour_str}.json"
    dated_path.write_text(json.dumps(report, indent=2))

    # Write latest.json (always overwritten as a regular file, not symlink)
    latest_path = REPORTS_DIR / "latest.json"
    if latest_path.is_symlink() or latest_path.exists():
        latest_path.unlink()
    latest_path.write_text(json.dumps(report, indent=2))

    print(f"Report written to {dated_path}")
    print(f"Latest updated at {latest_path}")

    return report


if __name__ == "__main__":
    generate()
