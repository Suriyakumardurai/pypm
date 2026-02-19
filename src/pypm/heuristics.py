from pathlib import Path  # noqa: F401
from typing import Set  # noqa: F401
import re
from .utils import log

def detect_django_channels(root_path):
    # type: (Path) -> Set[str]
    """
    Scans for Django Channels usage (daphne).
    """
    deps = set()  # type: Set[str]
    return deps

def detect_django_database(root_path):
    # type: (Path) -> Set[str]
    """
    Scans Django settings for database engines and returns implied drivers.
    """
    deps = set()  # type: Set[str]

    # 1. Find settings files
    settings_files = list(root_path.glob("**/settings.py"))
    settings_files.extend(root_path.glob("**/settings/*.py"))

    for settings_path in settings_files:
        if "site-packages" in str(settings_path) or ".venv" in str(settings_path):
            continue

        try:
            content = settings_path.read_text(encoding="utf-8")

            if re.search(r"['\"]ENGINE['\"]\s*:\s*['\"]django\.db\.backends\.postgresql['\"]", content):
                deps.add("psycopg2-binary")
            elif re.search(r"['\"]ENGINE['\"]\s*:\s*['\"]django\.db\.backends\.postgresql_psycopg2['\"]", content):
                deps.add("psycopg2-binary")
            elif re.search(r"['\"]ENGINE['\"]\s*:\s*['\"]django\.db\.backends\.mysql['\"]", content):
                deps.add("mysqlclient")
            elif re.search(r"['\"]ENGINE['\"]\s*:\s*['\"]django\.db\.backends\.oracle['\"]", content):
                deps.add("cx_Oracle")

            # Redis Cache
            if "django_redis" in content or "django.core.cache.backends.redis" in content:
                deps.add("django-redis")
                deps.add("redis")

        except Exception as e:
            log("Failed to parse settings file %s: %s" % (str(settings_path), str(e)), level="DEBUG")

    return deps

def run_heuristics(root_path, current_imports):
    # type: (Path, Set[str]) -> Set[str]
    """
    Runs all heuristic checks and returns additional dependencies.
    """
    additional_deps = set()  # type: Set[str]

    # Django
    if "django" in current_imports:
        additional_deps.update(detect_django_database(root_path))

    # FastAPI
    if "fastapi" in current_imports:
        asgi_servers = {"uvicorn", "hypercorn", "daphne", "gunicorn"}
        has_server = any(srv in current_imports for srv in asgi_servers)

        if not has_server:
            additional_deps.add("uvicorn[standard]")

    # Flask
    if "flask" in current_imports:
        if "gunicorn" not in current_imports and "uwsgi" not in current_imports:
            additional_deps.add("gunicorn")

    return additional_deps
