"""
Report Service — Generates HTML reports from analysis results.
Self-contained HTML with inline CSS (dark theme, print-friendly).
"""

from datetime import datetime, timezone


class ReportService:
    """Generates downloadable HTML reports from analysis results."""

    def generate_html(self, job_id: str, repo_url: str, results: dict,
                      optimization_score: int | None, health_grade: str | None,
                      context: dict | None = None) -> str:
        """Generate a self-contained HTML report."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        total_findings = sum(
            len(r.get("findings", [])) for r in results.values()
        )
        critical_count = sum(
            1 for r in results.values()
            for f in r.get("findings", [])
            if f.get("severity") == "critical"
        )
        high_count = sum(
            1 for r in results.values()
            for f in r.get("findings", [])
            if f.get("severity") == "high"
        )

        # Build findings HTML
        findings_html = ""
        for agent_name, agent_result in results.items():
            findings = agent_result.get("findings", [])
            if not findings:
                continue
            findings_html += f'<h3>{agent_name.replace("_", " ").title()} ({len(findings)} findings)</h3>\n'
            for f in findings[:15]:  # Cap per agent
                severity = f.get("severity", "info")
                color = {"critical": "#ef4444", "high": "#f97316", "medium": "#eab308", "low": "#3b82f6"}.get(severity, "#64748b")
                solution = f.get("solution", "")
                solution_code = f.get("solution_code", "")
                findings_html += f'''
                <div class="finding" style="border-left: 3px solid {color};">
                    <div class="finding-header">
                        <span class="severity" style="color: {color};">[{severity.upper()}]</span>
                        <span>{f.get("description", "")}</span>
                    </div>
                    {"<div class='file-path'>📄 " + f.get("file_path", "") + (":" + str(f.get("line_number", "")) if f.get("line_number") else "") + "</div>" if f.get("file_path") else ""}
                    {"<div class='solution'><strong>💡 Solution:</strong> " + solution + "</div>" if solution else ""}
                    {"<pre class='code'>" + solution_code + "</pre>" if solution_code else ""}
                </div>
                '''

        # Quick wins
        quick_wins_html = ""
        opt_result = results.get("repository_optimization", {})
        quick_wins = opt_result.get("metrics", {}).get("quick_wins", [])
        if quick_wins:
            quick_wins_html = "<h2>⚡ Quick Wins</h2><ul>"
            for win in quick_wins[:10]:
                if isinstance(win, dict):
                    quick_wins_html += f"<li><strong>{win.get('title', '')}</strong> — {win.get('description', '')}</li>"
                else:
                    quick_wins_html += f"<li>{win}</li>"
            quick_wins_html += "</ul>"

        # Sprint roadmap
        roadmap_html = ""
        roadmap = opt_result.get("metrics", {}).get("sprint_roadmap", [])
        if roadmap:
            roadmap_html = "<h2>🗺️ Sprint Roadmap</h2>"
            for item in roadmap:
                if isinstance(item, dict):
                    roadmap_html += f"<div class='sprint'><strong>Sprint {item.get('sprint', '?')}:</strong> {item.get('title', '')} — {item.get('description', '')}</div>"
                else:
                    roadmap_html += f"<div class='sprint'>{item}</div>"

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RepoGenius AI — Optimization Report</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
               background: #0f172a; color: #e2e8f0; padding: 2rem; line-height: 1.6; }}
        .container {{ max-width: 900px; margin: 0 auto; }}
        h1 {{ color: #60a5fa; margin-bottom: 0.5rem; font-size: 1.8rem; }}
        h2 {{ color: #94a3b8; margin: 2rem 0 1rem; font-size: 1.3rem; border-bottom: 1px solid #334155; padding-bottom: 0.5rem; }}
        h3 {{ color: #cbd5e1; margin: 1.5rem 0 0.8rem; font-size: 1.1rem; }}
        .header {{ background: #1e293b; border-radius: 12px; padding: 2rem; margin-bottom: 2rem; }}
        .score {{ font-size: 3rem; font-weight: bold; color: #60a5fa; }}
        .grade {{ display: inline-block; padding: 0.3rem 0.8rem; border-radius: 6px;
                  background: #1e40af; color: #bfdbfe; font-weight: bold; margin-left: 1rem; }}
        .meta {{ color: #64748b; margin-top: 0.5rem; font-size: 0.9rem; }}
        .stats {{ display: flex; gap: 2rem; margin-top: 1rem; flex-wrap: wrap; }}
        .stat {{ text-align: center; }}
        .stat-value {{ font-size: 1.5rem; font-weight: bold; color: #f8fafc; }}
        .stat-label {{ font-size: 0.8rem; color: #64748b; }}
        .finding {{ background: #1e293b; border-radius: 8px; padding: 1rem; margin: 0.8rem 0; }}
        .finding-header {{ font-size: 0.9rem; }}
        .severity {{ font-weight: bold; margin-right: 0.5rem; }}
        .file-path {{ font-family: monospace; font-size: 0.8rem; color: #64748b; margin-top: 0.3rem; }}
        .solution {{ margin-top: 0.5rem; padding: 0.5rem; background: #0f172a; border-radius: 4px;
                    font-size: 0.85rem; color: #86efac; }}
        .code {{ background: #0f172a; border: 1px solid #334155; border-radius: 4px;
                padding: 0.5rem; font-size: 0.8rem; color: #94a3b8; overflow-x: auto;
                white-space: pre-wrap; margin-top: 0.3rem; }}
        .sprint {{ background: #1e293b; border-radius: 6px; padding: 0.8rem; margin: 0.5rem 0; }}
        ul {{ padding-left: 1.5rem; }}
        li {{ margin: 0.5rem 0; }}
        .footer {{ text-align: center; color: #475569; margin-top: 3rem; font-size: 0.8rem; }}
        @media print {{ body {{ background: white; color: #1e293b; }}
                       .header {{ background: #f1f5f9; }} .finding {{ background: #f8fafc; border: 1px solid #e2e8f0; }} }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🧠 RepoGenius AI — Optimization Report</h1>
            <p class="meta">Repository: <strong>{repo_url}</strong></p>
            <p class="meta">Generated: {timestamp} | Job ID: {job_id}</p>
            <div class="stats">
                <div class="stat">
                    <div class="stat-value score">{optimization_score or 'N/A'}</div>
                    <div class="stat-label">Optimization Score</div>
                </div>
                <div class="stat">
                    <div class="stat-value"><span class="grade">{health_grade or 'N/A'}</span></div>
                    <div class="stat-label">Health Grade</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{total_findings}</div>
                    <div class="stat-label">Total Findings</div>
                </div>
                <div class="stat">
                    <div class="stat-value" style="color: #ef4444;">{critical_count}</div>
                    <div class="stat-label">Critical</div>
                </div>
                <div class="stat">
                    <div class="stat-value" style="color: #f97316;">{high_count}</div>
                    <div class="stat-label">High</div>
                </div>
            </div>
        </div>

        {quick_wins_html}
        {roadmap_html}

        <h2>🔍 Detailed Findings (with Solutions)</h2>
        {findings_html if findings_html else "<p>No findings detected — repository looks healthy!</p>"}

        <div class="footer">
            <p>Generated by RepoGenius AI v1.0.0 — AI-Powered Repository Optimization Platform</p>
        </div>
    </div>
</body>
</html>"""
        return html


report_service = ReportService()
