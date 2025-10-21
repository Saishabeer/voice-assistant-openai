#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path


def _load_env_file(env_path: Path, override: bool = True):
    """
    Minimal .env loader (no external deps).
    - Supports KEY=VALUE and 'export KEY=VALUE'.
    - Ignores empty lines and lines starting with '#'.
    - Strips surrounding quotes from VALUE.
    - If override=True (default), .env values replace existing env vars.
    - Set ENV_LOADER_DEBUG=1 to print masked keys loaded.
    """
    def _strip_export(line: str) -> str:
        line = line.strip()
        if line.lower().startswith("export "):
            return line[7:].lstrip()
        return line

    try:
        if not env_path.exists():
            return
        debug = os.environ.get("ENV_LOADER_DEBUG", "") in ("1", "true", "True")
        loaded_keys = []
        for raw in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = _strip_export(raw.strip())
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip("'").strip('"')
            if not key:
                continue
            if override or key not in os.environ:
                os.environ[key] = val
                loaded_keys.append(key)
        if debug and loaded_keys:
            def mask(v: str) -> str:
                if not v:
                    return ""
                if len(v) <= 8:
                    return "*" * len(v)
                return v[:4] + "…" + v[-4:]
            # Mask only a few sensitive ones if present
            sample = []
            for k in ("OPENAI_API_KEY", "POSTGRES_PASSWORD", "DJANGO_SECRET_KEY"):
                if k in os.environ:
                    sample.append(f"{k}={mask(os.environ.get(k) or '')}")
            print(f"[env] loaded {len(loaded_keys)} keys from {env_path.name}" + (f" | " + " | ".join(sample) if sample else ""))
    except Exception:
        # Non-fatal: proceed without .env if parsing fails
        pass


def main():
    """Run administrative tasks."""
    # Load .env from project root so OPENAI_API_KEY and others are available (and override old env values)
    project_root = Path(__file__).resolve().parent
    _load_env_file(project_root / ".env", override=True)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_assist.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
