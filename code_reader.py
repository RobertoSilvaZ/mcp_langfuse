"""Safe read-only browsing of a single configured source tree."""
import os
from pathlib import Path

ROOT = Path(os.environ.get("SOURCE_CODE_ROOT", "/workspace")).resolve()
EXTENSIONS = {".py", ".md", ".txt", ".ts", ".tsx", ".js", ".jsx", ".json", ".yaml", ".yml", ".toml", ".css", ".html", ".sql", ".sh"}
DENIED_PARTS = {".git", ".env", ".ssh", ".aws", ".npmrc", ".pypirc", "node_modules", ".venv", "venv", "__pycache__", ".next", "dist", "build", "coverage", "secrets", "credentials", ".idea"}
DENIED_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".crt", ".sqlite", ".db", ".lock")
MAX_FILE_BYTES = 128 * 1024
MAX_SCAN_FILES = 1000


def _permitted_parts(parts):
    for part in parts:
        lower = part.lower()
        if lower.startswith(".") or lower in DENIED_PARTS or lower.startswith(".env") or lower.endswith(DENIED_SUFFIXES):
            return False
    return True


def _safe_file(relative_path: str) -> Path:
    relative = Path(relative_path)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts or not _permitted_parts(relative.parts):
        raise ValueError("Path is outside the allowed source tree or forbidden")
    target = ROOT / relative
    # Reject symlinks at every level, even when symlink points inside workspace.
    current = ROOT
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("Symlink traversal is not allowed")
    resolved = target.resolve()
    if not resolved.is_relative_to(ROOT):
        raise ValueError("Path escapes workspace")
    if not resolved.is_file() or resolved.suffix.lower() not in EXTENSIONS:
        raise ValueError("Not an allowed source file")
    if resolved.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("File exceeds the 128 KiB limit")
    return resolved


def _files():
    if not ROOT.is_dir():
        raise ValueError("Source directory is not mounted")
    count = 0
    for base, dirs, filenames in os.walk(ROOT, followlinks=False):
        parent = Path(base)
        dirs[:] = sorted(d for d in dirs if _permitted_parts((d,)) and not (parent / d).is_symlink())
        for name in sorted(filenames):
            candidate = parent / name
            if candidate.is_symlink() or not _permitted_parts((name,)) or candidate.suffix.lower() not in EXTENSIONS:
                continue
            count += 1
            if count > MAX_SCAN_FILES:
                return
            if candidate.stat().st_size <= MAX_FILE_BYTES:
                yield candidate.relative_to(ROOT).as_posix()


def list_project_files(limit: int = 200) -> dict:
    """List supported safe source files (excluding hidden files and secret paths)."""
    bounded = max(1, min(limit, 500))
    files = []
    for name in _files():
        files.append(name)
        if len(files) == bounded:
            break
    return {"files": files, "returned": len(files), "limit": bounded}


def read_source_file(path: str, start_line: int = 1, max_lines: int = 200) -> dict:
    """Read a source file with line numbers, in a bounded range."""
    target = _safe_file(path)
    lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
    start = max(1, start_line)
    end = min(len(lines), start + max(1, min(max_lines, 400)) - 1)
    return {"path": path, "total_lines": len(lines), "start_line": start,
            "content": "\n".join(f"{i}: {lines[i-1]}" for i in range(start, end + 1))}


def search_in_code(query: str, limit: int = 30) -> dict:
    """Find literal, case-insensitive matches within safe source files."""
    if not query or len(query) > 200:
        raise ValueError("query must contain 1-200 characters")
    results = []
    capped = max(1, min(limit, 100))
    for name in _files():
        target = _safe_file(name)
        for line_number, line in enumerate(target.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if query.casefold() in line.casefold():
                results.append({"path": name, "line": line_number, "snippet": line[:300]})
                if len(results) >= capped:
                    return {"matches": results, "truncated": True}
    return {"matches": results, "truncated": False}


def get_project_structure(limit: int = 200) -> dict:
    """Return a flat safe tree of readable source paths."""
    return list_project_files(limit)
