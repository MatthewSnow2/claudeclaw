#!/home/apexaipc/projects/claudeclaw/venv/bin/python
"""
Multi-pass PR Code Review for Ravage.

Inspired by Anthropic's managed code review approach: multiple focused review
passes run in parallel, each looking for different issue classes. Findings are
posted as inline GitHub comments with severity labels.

Usage:
    python review_pr.py <owner/repo> <pr_number> [--auto-comment] [--dry-run]

Requires:
    - gh CLI authenticated (MatthewSnow2)
    - ANTHROPIC_API_KEY in ~/.env.shared
    - Python 3.11+

Cost tracking:
    Every review logs token usage + estimated cost to claudeclaw.db hive_mind table.
    Use the dashboard or `convolife` to monitor burn.
"""

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(os.path.expanduser("~/.env.shared"))

try:
    import anthropic
except ImportError:
    print("ERROR: anthropic package not installed. Run: pip install anthropic")
    sys.exit(1)


# -- Config ------------------------------------------------------------------

STORE_DIR = Path(__file__).resolve().parents[3] / "store"
DB_PATH = STORE_DIR / "claudeclaw.db"

# Model for review passes. Sonnet balances quality/cost.
REVIEW_MODEL = "claude-sonnet-4-20250514"

# Token pricing (per 1M tokens, as of 2026-03)
INPUT_PRICE_PER_M = 3.00   # $3/M input
OUTPUT_PRICE_PER_M = 15.00  # $15/M output

# Severity labels (match Anthropic's convention)
SEVERITY_CRITICAL = "critical"    # Must fix before merge
SEVERITY_MEDIUM = "medium"        # Should fix, not blocking
SEVERITY_LOW = "low"              # Suggestion/style
SEVERITY_PREEXISTING = "preexisting"  # Issue existed before this PR

MAX_DIFF_LINES = 3000  # Truncate very large diffs


# -- Data types --------------------------------------------------------------

@dataclass
class ReviewFinding:
    file: str
    line: int | None
    severity: str
    category: str  # security, bug, performance, style, architecture
    title: str
    description: str
    suggestion: str | None = None


@dataclass
class ReviewPass:
    name: str
    focus: str
    system_prompt: str
    findings: list[ReviewFinding] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class ReviewResult:
    repo: str
    pr_number: int
    pr_title: str
    total_findings: int
    critical_count: int
    medium_count: int
    low_count: int
    preexisting_count: int
    passes: list[ReviewPass]
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    duration_seconds: float = 0.0


# -- GitHub helpers ----------------------------------------------------------

def gh_run(args: list[str], check: bool = True) -> str:
    """Run a gh CLI command and return stdout."""
    result = subprocess.run(
        ["gh"] + args,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def fetch_pr_info(repo: str, pr_number: int) -> dict:
    """Fetch PR metadata via gh CLI."""
    raw = gh_run([
        "pr", "view", str(pr_number),
        "--repo", repo,
        "--json", "title,body,headRefName,baseRefName,files,additions,deletions,changedFiles,author",
    ])
    return json.loads(raw)


def fetch_pr_diff(repo: str, pr_number: int) -> str:
    """Fetch PR diff via gh CLI."""
    diff = gh_run(["pr", "diff", str(pr_number), "--repo", repo])
    lines = diff.split("\n")
    if len(lines) > MAX_DIFF_LINES:
        truncated = lines[:MAX_DIFF_LINES]
        truncated.append(f"\n... [TRUNCATED: {len(lines) - MAX_DIFF_LINES} lines omitted] ...")
        return "\n".join(truncated)
    return diff


def post_pr_comment(repo: str, pr_number: int, body: str) -> None:
    """Post a top-level comment on the PR."""
    gh_run(["pr", "comment", str(pr_number), "--repo", repo, "--body", body])


def post_review_comment(
    repo: str, pr_number: int, body: str, path: str, line: int
) -> None:
    """Post an inline review comment on a specific file/line."""
    # gh api is more reliable for inline comments than gh pr review
    gh_run([
        "api",
        f"repos/{repo}/pulls/{pr_number}/comments",
        "-f", f"body={body}",
        "-f", f"path={path}",
        "-F", f"line={line}",
        "-f", "commit_id=$(gh pr view {pr_number} --repo {repo} --json headRefOid -q .headRefOid)",
        "-f", "side=RIGHT",
    ], check=False)  # Don't fail the whole review if one comment fails


def get_pr_head_sha(repo: str, pr_number: int) -> str:
    """Get the HEAD commit SHA of the PR."""
    raw = gh_run([
        "pr", "view", str(pr_number),
        "--repo", repo,
        "--json", "headRefOid",
        "-q", ".headRefOid",
    ])
    return raw.strip()


def post_inline_comments(
    repo: str, pr_number: int, findings: list[ReviewFinding]
) -> int:
    """Post inline review comments for findings that have file+line info."""
    head_sha = get_pr_head_sha(repo, pr_number)
    posted = 0

    for f in findings:
        if not f.file or not f.line:
            continue

        severity_emoji = {
            SEVERITY_CRITICAL: "🔴",
            SEVERITY_MEDIUM: "🟡",
            SEVERITY_LOW: "🟣",
            SEVERITY_PREEXISTING: "⚫",
        }.get(f.severity, "⚪")

        body = f"{severity_emoji} **{f.severity.upper()}** | {f.category}\n\n"
        body += f"**{f.title}**\n\n{f.description}"
        if f.suggestion:
            body += f"\n\n**Suggestion:** {f.suggestion}"

        try:
            # Use the GitHub API directly for inline comments
            gh_run([
                "api",
                f"repos/{repo}/pulls/{pr_number}/comments",
                "-f", f"body={body}",
                "-f", f"path={f.file}",
                "-F", f"line={f.line}",
                "-f", f"commit_id={head_sha}",
                "-f", "side=RIGHT",
            ])
            posted += 1
        except RuntimeError as e:
            # Line might not be in the diff hunk. Skip silently.
            print(f"  [skip] Could not post comment on {f.file}:{f.line}: {e}")

    return posted


# -- Review passes -----------------------------------------------------------

REVIEW_PASSES = [
    ReviewPass(
        name="security",
        focus="Security vulnerabilities, injection risks, auth issues",
        system_prompt="""You are a security-focused code reviewer. Analyze the PR diff for:
- Injection vulnerabilities (SQL, command, XSS, template)
- Authentication/authorization bypasses
- Secrets or credentials in code
- Insecure cryptography or random number generation
- Path traversal or file access issues
- Unsafe deserialization
- Missing input validation on trust boundaries

Only report REAL issues with specific file and line references from the diff.
Do NOT report style issues, minor improvements, or theoretical concerns.
If you find nothing, return an empty findings array.""",
    ),
    ReviewPass(
        name="bugs",
        focus="Logic errors, edge cases, race conditions",
        system_prompt="""You are a bug-hunting code reviewer. Analyze the PR diff for:
- Logic errors and off-by-one mistakes
- Null/undefined handling gaps
- Race conditions in concurrent code
- Resource leaks (file handles, connections, memory)
- Error handling that swallows exceptions silently
- Type mismatches or unsafe casts
- Missing edge cases (empty arrays, zero values, boundary conditions)

Only report issues with specific file and line references from the diff.
Focus on bugs that could cause runtime failures or data corruption.
If you find nothing, return an empty findings array.""",
    ),
    ReviewPass(
        name="architecture",
        focus="Design patterns, maintainability, API contracts",
        system_prompt="""You are an architecture-focused code reviewer. Analyze the PR diff for:
- Violations of existing patterns in the codebase
- Breaking changes to public APIs or contracts
- Tight coupling that should be abstracted
- Missing error boundaries or fallback behavior
- Inconsistent naming or organization
- Dead code or unused imports
- Missing tests for new functionality

Only report substantive architectural concerns, not style preferences.
Reference specific files and lines from the diff.
If you find nothing, return an empty findings array.""",
    ),
]

FINDING_SCHEMA = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "file": {"type": "string", "description": "File path from diff header"},
                    "line": {"type": ["integer", "null"], "description": "Line number in the new file (right side of diff)"},
                    "severity": {"type": "string", "enum": ["critical", "medium", "low", "preexisting"]},
                    "category": {"type": "string", "enum": ["security", "bug", "performance", "style", "architecture"]},
                    "title": {"type": "string", "description": "One-line summary of the issue"},
                    "description": {"type": "string", "description": "Detailed explanation of the issue"},
                    "suggestion": {"type": ["string", "null"], "description": "How to fix it (optional)"},
                },
                "required": ["file", "line", "severity", "category", "title", "description"],
            },
        },
    },
    "required": ["findings"],
}


def run_review_pass(
    client: anthropic.Anthropic,
    review_pass: ReviewPass,
    pr_info: dict,
    diff: str,
) -> ReviewPass:
    """Run a single focused review pass against the PR diff."""
    pr_context = (
        f"PR Title: {pr_info['title']}\n"
        f"Branch: {pr_info['headRefName']} -> {pr_info['baseRefName']}\n"
        f"Author: {pr_info.get('author', {}).get('login', 'unknown')}\n"
        f"Changed files: {pr_info.get('changedFiles', '?')}, "
        f"+{pr_info.get('additions', '?')} -{pr_info.get('deletions', '?')}\n"
    )
    if pr_info.get("body"):
        pr_context += f"\nPR Description:\n{pr_info['body'][:500]}\n"

    user_msg = f"""Review this pull request diff. Focus ONLY on your specialty: {review_pass.focus}

{pr_context}

## Diff

```diff
{diff}
```

Return your findings as structured JSON. If you find no issues in your focus area, return {{"findings": []}}."""

    response = client.messages.create(
        model=REVIEW_MODEL,
        max_tokens=4096,
        system=review_pass.system_prompt + "\n\nIMPORTANT: Respond with ONLY valid JSON. No markdown fences, no explanation text outside the JSON.",
        messages=[{"role": "user", "content": user_msg}],
    )

    review_pass.input_tokens = response.usage.input_tokens
    review_pass.output_tokens = response.usage.output_tokens

    # Parse findings from response
    text = response.content[0].text

    # Strip markdown code fences if present (model sometimes wraps JSON)
    stripped_text = re.sub(r'^```(?:json)?\s*\n?', '', text.strip())
    stripped_text = re.sub(r'\n?```\s*$', '', stripped_text).strip()

    parsed = False
    for attempt_text in [stripped_text, text]:
        try:
            data = json.loads(attempt_text)
            for f in data.get("findings", []):
                review_pass.findings.append(ReviewFinding(
                    file=f.get("file", ""),
                    line=f.get("line"),
                    severity=f.get("severity", "low"),
                    category=f.get("category", review_pass.name),
                    title=f.get("title", ""),
                    description=f.get("description", ""),
                    suggestion=f.get("suggestion"),
                ))
            parsed = True
            break
        except json.JSONDecodeError:
            continue

    if not parsed:
        # Last resort: find the outermost JSON object
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            try:
                data = json.loads(json_match.group())
                for f in data.get("findings", []):
                    review_pass.findings.append(ReviewFinding(
                        file=f.get("file", ""),
                        line=f.get("line"),
                        severity=f.get("severity", "low"),
                        category=f.get("category", review_pass.name),
                        title=f.get("title", ""),
                        description=f.get("description", ""),
                        suggestion=f.get("suggestion"),
                    ))
            except json.JSONDecodeError:
                print(f"  [warn] Failed to parse JSON from {review_pass.name} pass")

    return review_pass


# -- Cost tracking -----------------------------------------------------------

def estimate_cost(input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost from token counts."""
    input_cost = (input_tokens / 1_000_000) * INPUT_PRICE_PER_M
    output_cost = (output_tokens / 1_000_000) * OUTPUT_PRICE_PER_M
    return round(input_cost + output_cost, 4)


def log_review_to_db(result: ReviewResult) -> None:
    """Log review cost and summary to claudeclaw.db hive_mind table."""
    if not DB_PATH.exists():
        print(f"  [warn] DB not found at {DB_PATH}, skipping cost log")
        return

    conn = sqlite3.connect(str(DB_PATH))
    try:
        now = int(time.time())
        summary = (
            f"PR Review: {result.repo}#{result.pr_number} - {result.pr_title[:60]}"
        )
        detail = (
            f"Findings: {result.total_findings} "
            f"(C:{result.critical_count} M:{result.medium_count} "
            f"L:{result.low_count} P:{result.preexisting_count}) | "
            f"Tokens: {result.total_input_tokens}in/{result.total_output_tokens}out | "
            f"Cost: ${result.total_cost_usd:.4f} | "
            f"Duration: {result.duration_seconds:.1f}s | "
            f"Passes: {', '.join(p.name for p in result.passes)}"
        )
        conn.execute(
            "INSERT INTO hive_mind (worker, event_type, summary, detail, cost_usd, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("ravage", "pr_review", summary, detail, result.total_cost_usd, now),
        )
        conn.commit()
        print(f"  [db] Logged review cost: ${result.total_cost_usd:.4f}")
    finally:
        conn.close()


# -- Summary formatting ------------------------------------------------------

def format_summary(result: ReviewResult) -> str:
    """Format a summary comment to post on the PR."""
    lines = [
        f"## Ravage Code Review",
        f"",
        f"**{result.repo}#{result.pr_number}** - {result.pr_title}",
        f"",
        f"| Severity | Count |",
        f"|----------|-------|",
    ]

    if result.critical_count:
        lines.append(f"| 🔴 Critical | {result.critical_count} |")
    if result.medium_count:
        lines.append(f"| 🟡 Medium | {result.medium_count} |")
    if result.low_count:
        lines.append(f"| 🟣 Low | {result.low_count} |")
    if result.preexisting_count:
        lines.append(f"| ⚫ Preexisting | {result.preexisting_count} |")
    if result.total_findings == 0:
        lines.append(f"| ✅ Clean | 0 |")

    lines.extend([
        f"",
        f"**Review passes:** {', '.join(p.name for p in result.passes)}",
        f"**Cost:** ${result.total_cost_usd:.4f} | "
        f"**Duration:** {result.duration_seconds:.1f}s | "
        f"**Tokens:** {result.total_input_tokens + result.total_output_tokens:,}",
        f"",
    ])

    # Group findings by file
    if result.total_findings > 0:
        findings_by_file: dict[str, list[ReviewFinding]] = {}
        for p in result.passes:
            for f in p.findings:
                findings_by_file.setdefault(f.file, []).append(f)

        lines.append("### Findings")
        lines.append("")
        for file_path, findings in sorted(findings_by_file.items()):
            lines.append(f"**`{file_path}`**")
            for f in findings:
                sev = {"critical": "🔴", "medium": "🟡", "low": "🟣", "preexisting": "⚫"}.get(f.severity, "⚪")
                line_ref = f"L{f.line}" if f.line else ""
                lines.append(f"- {sev} {line_ref} **{f.title}** ({f.category})")
            lines.append("")

    lines.append("---")
    lines.append("*Reviewed by Ravage (multi-pass code review agent)*")

    return "\n".join(lines)


def format_console_summary(result: ReviewResult) -> str:
    """Format a concise console summary for Telegram delivery."""
    lines = [
        f"PR Review: {result.repo}#{result.pr_number}",
        f"Title: {result.pr_title}",
        f"",
    ]

    if result.total_findings == 0:
        lines.append("Clean -- no issues found across all passes.")
    else:
        lines.append(f"Found {result.total_findings} issues:")
        if result.critical_count:
            lines.append(f"  Critical: {result.critical_count}")
        if result.medium_count:
            lines.append(f"  Medium: {result.medium_count}")
        if result.low_count:
            lines.append(f"  Low: {result.low_count}")
        if result.preexisting_count:
            lines.append(f"  Preexisting: {result.preexisting_count}")

        # List critical findings explicitly
        for p in result.passes:
            for f in p.findings:
                if f.severity == SEVERITY_CRITICAL:
                    lines.append(f"  >> {f.file}:{f.line or '?'} - {f.title}")

    lines.extend([
        f"",
        f"Cost: ${result.total_cost_usd:.4f} | Duration: {result.duration_seconds:.1f}s",
        f"Tokens: {result.total_input_tokens + result.total_output_tokens:,}",
    ])

    return "\n".join(lines)


# -- Main --------------------------------------------------------------------

def review_pr(
    repo: str,
    pr_number: int,
    auto_comment: bool = False,
    dry_run: bool = False,
) -> ReviewResult:
    """Run a full multi-pass code review on a PR."""
    start_time = time.time()

    print(f"Reviewing {repo}#{pr_number}...")
    print(f"  Fetching PR info...")
    pr_info = fetch_pr_info(repo, pr_number)
    pr_title = pr_info.get("title", "Untitled")
    print(f"  Title: {pr_title}")
    print(f"  Files: {pr_info.get('changedFiles', '?')}, "
          f"+{pr_info.get('additions', '?')} -{pr_info.get('deletions', '?')}")

    print(f"  Fetching diff...")
    diff = fetch_pr_diff(repo, pr_number)
    diff_lines = diff.count("\n")
    print(f"  Diff: {diff_lines} lines")

    if diff_lines == 0:
        print("  No diff content. Nothing to review.")
        return ReviewResult(
            repo=repo, pr_number=pr_number, pr_title=pr_title,
            total_findings=0, critical_count=0, medium_count=0,
            low_count=0, preexisting_count=0, passes=[],
        )

    client = anthropic.Anthropic()
    completed_passes: list[ReviewPass] = []

    for review_pass in REVIEW_PASSES:
        print(f"  Running {review_pass.name} pass...")
        completed = run_review_pass(client, review_pass, pr_info, diff)
        completed_passes.append(completed)
        print(f"    Found {len(completed.findings)} issues "
              f"({completed.input_tokens}in/{completed.output_tokens}out)")

    # Aggregate results
    all_findings = [f for p in completed_passes for f in p.findings]
    total_input = sum(p.input_tokens for p in completed_passes)
    total_output = sum(p.output_tokens for p in completed_passes)
    total_cost = estimate_cost(total_input, total_output)
    duration = time.time() - start_time

    result = ReviewResult(
        repo=repo,
        pr_number=pr_number,
        pr_title=pr_title,
        total_findings=len(all_findings),
        critical_count=sum(1 for f in all_findings if f.severity == SEVERITY_CRITICAL),
        medium_count=sum(1 for f in all_findings if f.severity == SEVERITY_MEDIUM),
        low_count=sum(1 for f in all_findings if f.severity == SEVERITY_LOW),
        preexisting_count=sum(1 for f in all_findings if f.severity == SEVERITY_PREEXISTING),
        passes=completed_passes,
        total_input_tokens=total_input,
        total_output_tokens=total_output,
        total_cost_usd=total_cost,
        duration_seconds=duration,
    )

    # Log to DB
    if not dry_run:
        log_review_to_db(result)

    # Post to GitHub
    if auto_comment and not dry_run:
        print(f"  Posting summary comment to PR...")
        summary = format_summary(result)
        post_pr_comment(repo, pr_number, summary)

        if all_findings:
            print(f"  Posting {len(all_findings)} inline comments...")
            posted = post_inline_comments(repo, pr_number, all_findings)
            print(f"  Posted {posted}/{len(all_findings)} inline comments")
    elif dry_run:
        print("\n[DRY RUN] Would post this summary:\n")
        print(format_summary(result))

    # Console output
    print(f"\n{format_console_summary(result)}")

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-pass PR code review")
    parser.add_argument("repo", help="GitHub repo (owner/name)")
    parser.add_argument("pr_number", type=int, help="PR number")
    parser.add_argument(
        "--auto-comment", action="store_true",
        help="Post review summary and inline comments to GitHub",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Run review but don't post comments or log to DB",
    )
    args = parser.parse_args()

    review_pr(args.repo, args.pr_number, args.auto_comment, args.dry_run)


if __name__ == "__main__":
    main()
