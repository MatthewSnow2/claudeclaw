const db = require("better-sqlite3")("/home/apexaipc/projects/claudeclaw/store/claudeclaw.db");
const session = db.prepare("SELECT * FROM sessions ORDER BY updated_at DESC LIMIT 1").get();
if (!session) { console.log("No session"); process.exit(0); }
console.log("Session:", session.session_id);
console.log("Chat:", session.chat_id);

const latest = db.prepare("SELECT * FROM token_usage WHERE session_id = ? ORDER BY created_at DESC LIMIT 1").get(session.session_id);
const totals = db.prepare("SELECT COUNT(*) as turns, SUM(input_tokens) as ti, SUM(output_tokens) as to2, SUM(cost_usd) as cost FROM token_usage WHERE session_id = ?").get(session.session_id);
const compactions = db.prepare("SELECT COUNT(*) as cnt FROM token_usage WHERE session_id = ? AND did_compact = 1").get(session.session_id);

if (latest) {
  const cs = latest.cache_read || 0;
  const pct = (cs / 200000 * 100).toFixed(1);
  const rem = 200000 - cs;
  console.log("---");
  console.log("Context:", pct + "% used | ~" + Math.round(rem / 1000) + "k remaining");
  console.log("Last cache_read:", cs.toLocaleString());
}
if (totals) {
  console.log("Turns:", totals.turns);
  console.log("Total in:", (totals.ti || 0).toLocaleString());
  console.log("Total out:", (totals.to2 || 0).toLocaleString());
  console.log("Cost: $" + (totals.cost || 0).toFixed(4));
}
console.log("Compactions:", compactions ? compactions.cnt : 0);
