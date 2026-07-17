"""
SecurityAgent — Scans for hardcoded secrets using regex patterns.
Detects API keys, passwords, tokens, and other sensitive data.
"""

import os
import re

from ..base import BaseAgent
from ..payloads import AgentInputPayload, AgentOutputPayload, AgentFinding


# Regex patterns for secret detection — each includes a solution
SECRET_PATTERNS: list[tuple[str, str, str, str, str]] = [
    # (pattern_name, regex, severity, solution, solution_code)
    (
        "AWS Access Key",
        r"AKIA[0-9A-Z]{16}",
        "critical",
        "Move AWS credentials to environment variables or AWS IAM roles. Never commit access keys to source control. Use aws-vault or AWS SSO for local development.",
        "# Instead of hardcoding:\n# aws_key = 'AKIAIOSFODNN7EXAMPLE'\n\n# Use environment variables:\nimport os\naws_key = os.environ.get('AWS_ACCESS_KEY_ID')",
    ),
    (
        "AWS Secret Key",
        r"(?i)aws_secret_access_key\s*[=:]\s*['\"]?[\w/+=]{40}",
        "critical",
        "Store AWS secret keys in environment variables, AWS Secrets Manager, or use IAM roles. Rotate the exposed key immediately via the AWS console.",
        "# Use environment variable:\nimport os\naws_secret = os.environ.get('AWS_SECRET_ACCESS_KEY')\n\n# Or use boto3 default credential chain:\nimport boto3\nclient = boto3.client('s3')  # auto-finds credentials",
    ),
    (
        "Generic API Key",
        r"(?i)(api[_-]?key|apikey)\s*[=:]\s*['\"]?[\w-]{20,}",
        "high",
        "Move API keys to a .env file (excluded from git via .gitignore) and load them via environment variables. Consider using a secrets manager for production.",
        "# .env file (add to .gitignore):\n# API_KEY=your-key-here\n\n# In your code:\nfrom dotenv import load_dotenv\nimport os\nload_dotenv()\napi_key = os.environ['API_KEY']",
    ),
    (
        "Generic Secret",
        r"(?i)(secret|password|passwd|pwd)\s*[=:]\s*['\"]?[^\s'\"]{8,}",
        "high",
        "Never hardcode passwords or secrets. Use environment variables, .env files, or a secrets manager (HashiCorp Vault, AWS Secrets Manager, Azure Key Vault).",
        "# Bad:\n# db_password = 'super_secret_123'\n\n# Good:\nimport os\ndb_password = os.environ.get('DB_PASSWORD')\nif not db_password:\n    raise ValueError('DB_PASSWORD environment variable not set')",
    ),
    (
        "Private Key",
        r"-----BEGIN (RSA |EC |DSA )?PRIVATE KEY-----",
        "critical",
        "Remove private keys from source code immediately. Store them in a secure key management system. If this key was committed to git history, consider it compromised and rotate it.",
        "# Store keys as files OUTSIDE the repo:\n# /etc/ssl/private/my-key.pem\n\n# Reference via environment variable:\nimport os\nkey_path = os.environ.get('PRIVATE_KEY_PATH', '/etc/ssl/private/key.pem')\nwith open(key_path) as f:\n    private_key = f.read()",
    ),
    (
        "GitHub Token",
        r"gh[ps]_[A-Za-z0-9_]{36,}",
        "critical",
        "Revoke this GitHub token immediately at github.com/settings/tokens. Use GITHUB_TOKEN environment variable instead. For CI/CD, use GitHub Actions secrets.",
        "# Revoke at: https://github.com/settings/tokens\n\n# Use environment variable:\nimport os\ngithub_token = os.environ.get('GITHUB_TOKEN')\n\n# In GitHub Actions, it's automatic:\n# ${{ secrets.GITHUB_TOKEN }}",
    ),
    (
        "Generic Token",
        r"(?i)(token|bearer)\s*[=:]\s*['\"]?[\w-]{20,}",
        "high",
        "Move tokens to environment variables. For frontend apps, use a backend proxy to avoid exposing tokens. Rotate the token if it was committed to a public repository.",
        "# Use environment variable:\nimport os\ntoken = os.environ.get('AUTH_TOKEN')\n\n# For requests:\nheaders = {'Authorization': f'Bearer {token}'}",
    ),
    (
        "Database URL with Password",
        r"(?i)(postgres|mysql|mongodb)://\w+:[^@\s]+@",
        "critical",
        "Move database connection strings to environment variables. Use connection pooling services or IAM authentication where possible. Rotate database password if exposed.",
        "# .env file:\n# DATABASE_URL=postgresql://user:pass@host:5432/db\n\n# In code:\nimport os\ndb_url = os.environ.get('DATABASE_URL')\n\n# Or use individual parts:\nDB_HOST = os.environ.get('DB_HOST', 'localhost')\nDB_PASSWORD = os.environ.get('DB_PASSWORD')",
    ),
    (
        "Hardcoded IP Address",
        r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b",
        "low",
        "Use configuration files or environment variables for IP addresses. Hardcoded IPs make deployments inflexible and may expose internal infrastructure.",
        "# Instead of: host = '192.168.1.100'\n# Use:\nimport os\nhost = os.environ.get('SERVICE_HOST', 'localhost')",
    ),
    (
        "JWT Secret",
        r"(?i)jwt[_-]?secret\s*[=:]\s*['\"]?[^\s'\"]{8,}",
        "high",
        "Generate a strong random JWT secret (at least 256 bits) and store it as an environment variable. Rotate immediately if exposed. Use: python -c \"import secrets; print(secrets.token_hex(32))\"",
        "# Generate a strong secret:\n# python -c \"import secrets; print(secrets.token_hex(32))\"\n\n# Store in environment:\nimport os\nJWT_SECRET = os.environ.get('JWT_SECRET')\nif not JWT_SECRET or len(JWT_SECRET) < 32:\n    raise ValueError('JWT_SECRET must be at least 32 characters')",
    ),
]

# File extensions to scan
SCANNABLE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rb",
    ".php", ".env", ".yml", ".yaml", ".json", ".toml", ".cfg",
    ".conf", ".ini", ".sh", ".bash", ".properties",
}

# Directories to skip
SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", "vendor", ".next",
}

# Files to skip (likely false positives)
SKIP_FILES = {"package-lock.json", "yarn.lock", "poetry.lock"}


class SecurityAgent(BaseAgent):
    name = "security"
    version = "1.0.0"
    dependencies = []

    async def run(self, payload: AgentInputPayload) -> AgentOutputPayload:
        repo_path = payload.repo_path
        findings: list[AgentFinding] = []
        files_scanned = 0

        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

            for filename in files:
                if filename in SKIP_FILES:
                    continue

                _, ext = os.path.splitext(filename)
                if ext.lower() not in SCANNABLE_EXTENSIONS:
                    continue

                filepath = os.path.join(root, filename)
                rel_path = os.path.relpath(filepath, repo_path)
                files_scanned += 1

                try:
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        for line_num, line in enumerate(f, 1):
                            # Skip comments and very long lines
                            stripped = line.strip()
                            if len(stripped) > 1000:
                                continue

                            for pattern_name, pattern, severity, solution, solution_code in SECRET_PATTERNS:
                                if re.search(pattern, line):
                                    findings.append(AgentFinding(
                                        severity=severity,
                                        description=f"Potential {pattern_name} detected",
                                        file_path=rel_path,
                                        line_number=line_num,
                                        category="secret_detection",
                                        solution=solution,
                                        solution_code=solution_code,
                                        solution_reference="https://owasp.org/Top10/A07_2021-Identification_and_Authentication_Failures/",
                                        cwe_id="CWE-798",
                                        owasp_category="A07:2021",
                                        exploitability="high" if severity == "critical" else "medium",
                                        fix_difficulty="easy",
                                        estimated_fix_minutes=5,
                                    ))
                                    break  # One finding per line
                except (OSError, UnicodeDecodeError):
                    continue

        summary = (
            f"Scanned {files_scanned} files. "
            f"Found {len(findings)} potential security issues."
        )

        return AgentOutputPayload(
            agent=self.name,
            status="success",
            findings=findings,
            metrics={
                "files_scanned": files_scanned,
                "secrets_found": len(findings),
                "critical_count": sum(1 for f in findings if f.severity == "critical"),
                "high_count": sum(1 for f in findings if f.severity == "high"),
            },
            summary=summary,
        )
