"""
Diff Service — Compare two analysis runs of the same repository.
Shows what improved, what regressed, and what's new/resolved.
"""

from ...infrastructure.storage.history import history_store


class DiffService:
    """Compares two analysis results."""

    def compare(self, job_id_a: str, job_id_b: str) -> dict:
        """
        Compare two analyses. job_a is the older run, job_b is the newer run.
        Returns score delta, new findings, resolved findings, and metrics delta.
        """
        entry_a = history_store.get_by_id(job_id_a)
        entry_b = history_store.get_by_id(job_id_b)

        if not entry_a or not entry_b:
            return {"error": "One or both analyses not found"}

        score_a = entry_a.get("optimization_score") or 0
        score_b = entry_b.get("optimization_score") or 0

        findings_a = self._extract_all_findings(entry_a.get("results", {}))
        findings_b = self._extract_all_findings(entry_b.get("results", {}))

        # Fingerprint findings by file_path + description for matching
        set_a = {self._fingerprint(f) for f in findings_a}
        set_b = {self._fingerprint(f) for f in findings_b}

        new_fps = set_b - set_a
        resolved_fps = set_a - set_b

        new_findings = [f for f in findings_b if self._fingerprint(f) in new_fps]
        resolved_findings = [f for f in findings_a if self._fingerprint(f) in resolved_fps]

        return {
            "job_a": {"id": job_id_a, "timestamp": entry_a.get("timestamp"), "score": score_a},
            "job_b": {"id": job_id_b, "timestamp": entry_b.get("timestamp"), "score": score_b},
            "score_delta": score_b - score_a,
            "findings_count_a": len(findings_a),
            "findings_count_b": len(findings_b),
            "new_findings": new_findings[:20],  # Cap at 20
            "resolved_findings": resolved_findings[:20],
            "new_count": len(new_fps),
            "resolved_count": len(resolved_fps),
            "improvement": score_b > score_a,
            "summary": self._generate_summary(score_a, score_b, len(new_fps), len(resolved_fps)),
        }

    def _extract_all_findings(self, results: dict) -> list[dict]:
        """Extract all findings from all agents."""
        all_findings = []
        for agent_name, agent_result in results.items():
            if isinstance(agent_result, dict):
                findings = agent_result.get("findings", [])
                for f in findings:
                    if isinstance(f, dict):
                        f["_agent"] = agent_name
                        all_findings.append(f)
        return all_findings

    def _fingerprint(self, finding: dict) -> str:
        """Create a unique identifier for a finding."""
        return f"{finding.get('file_path', '')}|{finding.get('description', '')}|{finding.get('category', '')}"

    def _generate_summary(self, score_a: int, score_b: int, new: int, resolved: int) -> str:
        delta = score_b - score_a
        if delta > 0:
            return f"Score improved by {delta} points. {resolved} issues resolved, {new} new issues found."
        elif delta < 0:
            return f"Score decreased by {abs(delta)} points. {new} new issues found, {resolved} resolved."
        else:
            return f"Score unchanged. {resolved} issues resolved, {new} new issues appeared."


diff_service = DiffService()
