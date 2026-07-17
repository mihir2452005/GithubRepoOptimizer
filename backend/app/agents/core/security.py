"""
SecurityAgent — Production-grade security scanner.
Detects hardcoded secrets, dangerous function usage, SQL injection patterns,
and insecure practices. Reduces false positives by skipping test/example files
and placeholder values.
"""

import os
import re

from ..base import BaseAgent
from ..payloads import AgentInputPayload, AgentOutputPayload, AgentFinding


# Directories to skip entirely (test/example code)
SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", "vendor", ".next", "target",
    "test", "tests", "__tests__", "spec", "fixtures",
    "mock", "mocks", "example", "examples", "docs",
}

# Files to skip (likely false positives)
SKIP_FILES = {"package-lock.json", "yarn.lock", "poetry.lock", "pnpm-lock.yaml"}

# File extensions to scan
SCANNABLE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rb",
    ".php", ".env", ".yml", ".yaml", ".json", ".toml", ".cfg",
    ".conf", ".ini", ".sh", ".bash", ".properties",
}

# Max file size to scan (100KB) — skip likely generated/minified files
MAX_FILE_SIZE = 100 * 1024

# Placeholder indicators — lines containing these are likely not real secrets
PLACEHOLDER_INDICATORS = [
    "example", "your-", "xxx", "placeholder", "changeme",
    "todo", "replace_me", "insert_here", "dummy", "sample",
    "fake", "test_", "mock_",
]


# === SECRET PATTERNS ===
SECRET_PATTERNS: list[tuple[str, str, str, str, str]] = [
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
        "JWT Secret",
        r"(?i)jwt[_-]?secret\s*[=:]\s*['\"]?[^\s'\"]{8,}",
        "high",
        "Generate a strong random JWT secret (at least 256 bits) and store it as an environment variable. Rotate immediately if exposed.",
        "# Generate a strong secret:\n# python -c \"import secrets; print(secrets.token_hex(32))\"\n\nimport os\nJWT_SECRET = os.environ.get('JWT_SECRET')\nif not JWT_SECRET or len(JWT_SECRET) < 32:\n    raise ValueError('JWT_SECRET must be at least 32 characters')",
    ),
]

# === DANGEROUS FUNCTION PATTERNS ===
DANGEROUS_PATTERNS: list[tuple[str, str, str, str, str, str]] = [
    # (name, regex, severity, category, solution, solution_code)
    (
        "eval() usage",
        r"\beval\s*\(",
        "high",
        "dangerous_function",
        "eval() executes arbitrary code and is a major security risk. Use ast.literal_eval() for safe evaluation of Python literals, or json.loads() for JSON data. Never pass user input to eval().",
        "# DANGEROUS:\n# result = eval(user_input)\n\n# SAFE alternatives:\nimport ast\nimport json\n\n# For Python literals (strings, numbers, tuples, lists, dicts):\nresult = ast.literal_eval(data_string)\n\n# For JSON data:\nresult = json.loads(json_string)\n\n# For math expressions, use a safe parser:\n# pip install simpleeval\nfrom simpleeval import simple_eval\nresult = simple_eval(expression)",
    ),
    (
        "subprocess with shell=True",
        r"subprocess\.(call|run|Popen)\s*\([^)]*shell\s*=\s*True",
        "high",
        "dangerous_function",
        "shell=True passes the command through the system shell, enabling shell injection attacks. Use a list of arguments instead, which bypasses the shell entirely.",
        "# DANGEROUS — vulnerable to shell injection:\n# subprocess.run(f'ls {user_input}', shell=True)\n\n# SAFE — pass arguments as a list:\nimport subprocess\nimport shlex\n\n# Option 1: List of args (preferred)\nsubprocess.run(['ls', '-la', directory], check=True)\n\n# Option 2: If you need to parse a command string safely:\ncmd = shlex.split(f'ls -la {shlex.quote(directory)}')\nsubprocess.run(cmd, check=True)",
    ),
    (
        "HTTP URL in code (not HTTPS)",
        r"""(?<!['"/])(https?://)(?=http://)|(["'])http://(?!localhost|127\.0\.0\.1|0\.0\.0\.0)[^'"]+\2""",
        "medium",
        "insecure_connection",
        "Use HTTPS for all external connections to prevent man-in-the-middle attacks. HTTP transmits data in plaintext, exposing it to interception.",
        "# INSECURE:\n# url = 'http://api.example.com/data'\n\n# SECURE:\nurl = 'https://api.example.com/data'\n\n# For development, allow HTTP only for localhost:\nimport os\nbase_url = os.environ.get('API_URL', 'https://api.example.com')",
    ),
    (
        "SQL Injection — String Concatenation",
        r"""(?i)(execute|cursor\.execute|query)\s*\(\s*[f'"]+.*(%s|\{|\+\s*\w+).*(?:SELECT|INSERT|UPDATE|DELETE|DROP|WHERE)""",
        "critical",
        "sql_injection",
        "Never build SQL queries by concatenating user input. Use parameterized queries (placeholders) which separate SQL code from data, preventing injection attacks.",
        "# VULNERABLE to SQL injection:\n# cursor.execute(f\"SELECT * FROM users WHERE id = {user_id}\")\n# cursor.execute(\"SELECT * FROM users WHERE id = \" + user_id)\n\n# SAFE — parameterized queries:\ncursor.execute(\"SELECT * FROM users WHERE id = %s\", (user_id,))\n\n# With SQLAlchemy:\nfrom sqlalchemy import text\nresult = session.execute(\n    text(\"SELECT * FROM users WHERE id = :uid\"),\n    {\"uid\": user_id}\n)",
    ),
    (
        "SQL Injection — f-string in query",
        r"""(?i)(?:execute|query)\s*\(\s*f['\"].*(?:SELECT|INSERT|UPDATE|DELETE|DROP|WHERE)""",
        "critical",
        "sql_injection",
        "f-strings in SQL queries are vulnerable to SQL injection. Always use parameterized queries with placeholders to safely pass values.",
        "# VULNERABLE:\n# db.execute(f\"SELECT * FROM users WHERE email = '{email}'\")\n\n# SAFE:\ndb.execute(\"SELECT * FROM users WHERE email = ?\", (email,))\n\n# With an ORM (recommended):\nuser = User.query.filter_by(email=email).first()",
    ),
    (
        "pickle.loads() on untrusted data",
        r"pickle\.(loads?|Unpickler)\s*\(",
        "high",
        "dangerous_function",
        "pickle.loads() can execute arbitrary code during deserialization. Never unpickle data from untrusted sources. Use JSON or MessagePack for safe serialization.",
        "# DANGEROUS — arbitrary code execution:\n# import pickle\n# data = pickle.loads(untrusted_bytes)\n\n# SAFE alternatives:\nimport json\ndata = json.loads(trusted_json_string)\n\n# For binary data:\nimport msgpack  # pip install msgpack\ndata = msgpack.unpackb(binary_data)\n\n# If you MUST use pickle, restrict allowed classes:\nimport pickle\nimport io\n\nclass RestrictedUnpickler(pickle.Unpickler):\n    def find_class(self, module, name):\n        # Only allow safe classes\n        raise pickle.UnpicklingError(f\"Blocked: {module}.{name}\")",
    ),
]

# Simpler HTTP pattern for non-comment lines
HTTP_PATTERN = re.compile(r"""['\"](http://(?!localhost|127\.0\.0\.1|0\.0\.0\.0)[^'"]+)['\"]""")


class SecurityAgent(BaseAgent):
    name = "security"
    version = "2.0.0"
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

                # Skip files > 100KB (likely generated/minified)
                try:
                    file_size = os.path.getsize(filepath)
                    if file_size > MAX_FILE_SIZE:
                        continue
                except OSError:
                    continue

                files_scanned += 1

                try:
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                except (OSError, UnicodeDecodeError):
                    continue

                lines = content.splitlines()

                for line_num, line in enumerate(lines, 1):
                    stripped = line.strip()
                    # Skip very long lines
                    if len(stripped) > 1000:
                        continue

                    # Skip comment-only lines for some checks
                    is_comment = stripped.startswith(("#", "//", "*", "/*", "'''", '"""'))

                    # Skip lines that look like placeholders
                    if self._is_placeholder_line(stripped):
                        continue

                    # Check secret patterns
                    for pattern_name, pattern, severity, solution, solution_code in SECRET_PATTERNS:
                        if re.search(pattern, line):
                            # Build REAL fix code using actual file path and line content
                            real_fix = self._build_real_secret_fix(
                                pattern_name, rel_path, line_num, stripped, solution_code
                            )
                            findings.append(AgentFinding(
                                severity=severity,
                                description=f"Potential {pattern_name} detected in {rel_path} at line {line_num}",
                                file_path=rel_path,
                                line_number=line_num,
                                category="secret_detection",
                                solution=solution,
                                solution_code=real_fix,
                                solution_reference="https://owasp.org/Top10/A07_2021-Identification_and_Authentication_Failures/",
                                cwe_id="CWE-798",
                                owasp_category="A07:2021",
                                exploitability="high" if severity == "critical" else "medium",
                                fix_difficulty="easy",
                                estimated_fix_minutes=5,
                            ))
                            break  # One finding per line

                    # Check dangerous function patterns (skip comments)
                    if not is_comment:
                        for name, pattern, severity, category, solution, solution_code in DANGEROUS_PATTERNS:
                            if re.search(pattern, line):
                                # Build real fix using actual line content
                                real_fix = self._build_real_dangerous_fix(
                                    name, rel_path, line_num, stripped, solution_code
                                )
                                findings.append(AgentFinding(
                                    severity=severity,
                                    description=f"Dangerous pattern: {name} in {rel_path}:{line_num}",
                                    file_path=rel_path,
                                    line_number=line_num,
                                    category=category,
                                    solution=solution,
                                    solution_code=real_fix,
                                    solution_reference="https://owasp.org/Top10/A03_2021-Injection/",
                                    cwe_id="CWE-78" if "subprocess" in name else "CWE-94",
                                    owasp_category="A03:2021",
                                    exploitability="high",
                                    fix_difficulty="medium",
                                    estimated_fix_minutes=15,
                                ))
                                break

                    # Check for HTTP URLs in non-comment lines
                    if not is_comment and "http://" in line:
                        http_match = HTTP_PATTERN.search(line)
                        if http_match:
                            findings.append(AgentFinding(
                                severity="medium",
                                description=f"Insecure HTTP URL: {http_match.group(1)[:60]}...",
                                file_path=rel_path,
                                line_number=line_num,
                                category="insecure_connection",
                                solution="Use HTTPS for all external connections to prevent man-in-the-middle attacks. HTTP transmits data in plaintext.",
                                solution_code="# Replace http:// with https://\n# Ensure the server supports TLS/SSL\nurl = 'https://...'  # Always use HTTPS",
                                fix_difficulty="easy",
                                estimated_fix_minutes=2,
                            ))

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
                "secrets_found": sum(1 for f in findings if f.category == "secret_detection"),
                "dangerous_functions": sum(1 for f in findings if f.category == "dangerous_function"),
                "sql_injections": sum(1 for f in findings if f.category == "sql_injection"),
                "insecure_connections": sum(1 for f in findings if f.category == "insecure_connection"),
                "critical_count": sum(1 for f in findings if f.severity == "critical"),
                "high_count": sum(1 for f in findings if f.severity == "high"),
            },
            summary=summary,
        )

    def _is_placeholder_line(self, line: str) -> bool:
        """Check if a line contains placeholder/example values (not real secrets)."""
        line_lower = line.lower()
        return any(indicator in line_lower for indicator in PLACEHOLDER_INDICATORS)

    def _build_real_secret_fix(self, pattern_name: str, file_path: str, line_num: int,
                               original_line: str, generic_fix: str) -> str:
        """Build a REAL copy-paste-ready fix that references the actual file and line."""
        # Extract the variable name from the line (e.g., `api_key = "..."` → `api_key`)
        var_match = re.match(r"^\s*(?:const|let|var|export)?\s*(\w+)\s*[=:]", original_line)
        var_name = var_match.group(1) if var_match else "SECRET_VALUE"
        env_var_name = var_name.upper().replace("-", "_")

        return (
            f"# File: {file_path}, Line: {line_num}\n"
            f"# CURRENT (INSECURE):\n"
            f"# {original_line.strip()}\n"
            f"#\n"
            f"# FIX — Replace with environment variable:\n"
            f"import os\n"
            f"{var_name} = os.environ.get('{env_var_name}')\n"
            f"if not {var_name}:\n"
            f"    raise ValueError('{env_var_name} environment variable is not set')\n"
            f"\n"
            f"# Then add to your .env file (DO NOT commit .env to git):\n"
            f"# {env_var_name}=<your-actual-value-here>\n"
            f"\n"
            f"# And add .env to .gitignore:\n"
            f"# echo '.env' >> .gitignore"
        )

    def _build_real_dangerous_fix(self, pattern_name: str, file_path: str, line_num: int,
                                   original_line: str, generic_fix: str) -> str:
        """Build a REAL copy-paste-ready fix for dangerous function usage."""
        if "eval" in pattern_name.lower():
            return (
                f"# File: {file_path}, Line: {line_num}\n"
                f"# CURRENT (DANGEROUS):\n"
                f"# {original_line.strip()}\n"
                f"#\n"
                f"# FIX — Replace eval() with safe alternative:\n"
                f"import ast\n"
                f"import json\n"
                f"\n"
                f"# If parsing Python literals (strings, numbers, lists, dicts):\n"
                f"result = ast.literal_eval(data_string)\n"
                f"\n"
                f"# If parsing JSON:\n"
                f"result = json.loads(json_string)"
            )
        elif "subprocess" in pattern_name.lower():
            # Extract the command from the line if possible
            return (
                f"# File: {file_path}, Line: {line_num}\n"
                f"# CURRENT (DANGEROUS - shell injection risk):\n"
                f"# {original_line.strip()}\n"
                f"#\n"
                f"# FIX — Use list arguments instead of shell=True:\n"
                f"import subprocess\n"
                f"\n"
                f"# Replace shell=True with a list of arguments:\n"
                f"result = subprocess.run(\n"
                f"    ['command', 'arg1', 'arg2'],  # split into list\n"
                f"    capture_output=True,\n"
                f"    text=True,\n"
                f"    check=True\n"
                f")"
            )
        elif "sql" in pattern_name.lower():
            return (
                f"# File: {file_path}, Line: {line_num}\n"
                f"# CURRENT (SQL INJECTION RISK):\n"
                f"# {original_line.strip()}\n"
                f"#\n"
                f"# FIX — Use parameterized query:\n"
                f"cursor.execute(\n"
                f"    \"SELECT * FROM table WHERE column = %s\",\n"
                f"    (user_value,)  # pass values as tuple parameter\n"
                f")\n"
                f"\n"
                f"# Or with SQLAlchemy:\n"
                f"from sqlalchemy import text\n"
                f"result = session.execute(\n"
                f"    text(\"SELECT * FROM table WHERE column = :val\"),\n"
                f"    {{\"val\": user_value}}\n"
                f")"
            )
        elif "pickle" in pattern_name.lower():
            return (
                f"# File: {file_path}, Line: {line_num}\n"
                f"# CURRENT (ARBITRARY CODE EXECUTION RISK):\n"
                f"# {original_line.strip()}\n"
                f"#\n"
                f"# FIX — Replace pickle with JSON:\n"
                f"import json\n"
                f"\n"
                f"# Serialize:\n"
                f"with open('data.json', 'w') as f:\n"
                f"    json.dump(data, f)\n"
                f"\n"
                f"# Deserialize:\n"
                f"with open('data.json', 'r') as f:\n"
                f"    data = json.load(f)"
            )
        else:
            # Generic but still includes the actual file/line context
            return (
                f"# File: {file_path}, Line: {line_num}\n"
                f"# CURRENT:\n"
                f"# {original_line.strip()}\n"
                f"#\n"
                f"# FIX:\n"
                f"{generic_fix}"
            )
