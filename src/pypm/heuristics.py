from pathlib import Path
from typing import Set
import re
from .utils import log

def detect_django_channels(root_path: Path) -> Set[str]:
    """
    Scans for Django Channels usage (daphne).
    """
    deps: Set[str] = set()
    return deps

def detect_django_database(root_path: Path) -> Set[str]:
    """
    Scans Django settings for database engines and returns implied drivers.
    """
    deps = set()
    
    # 1. Find settings files
    # Heuristic: Match *settings.py or settings/*.py
    settings_files = list(root_path.glob("**/settings.py"))
    settings_files.extend(root_path.glob("**/settings/*.py"))
    
    for settings_path in settings_files:
        if "site-packages" in str(settings_path) or ".venv" in str(settings_path):
            continue
            
        try:
            content = settings_path.read_text(encoding="utf-8")
            
            # Simple Regex for ENGINE
            # 'ENGINE': 'django.db.backends.postgresql'
            # "ENGINE": "django.db.backends.mysql"
            
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
            log(f"Failed to parse settings file {settings_path}: {e}", level="DEBUG")
            
    return deps

def run_heuristics(root_path: Path, current_imports: Set[str]) -> Set[str]:
    """
    Runs all heuristic checks and returns additional dependencies.
    """
    additional_deps = set()
    
    # Django
    if "django" in current_imports:
        # DB drivers
        additional_deps.update(detect_django_database(root_path))
        
    # FastAPI
    if "fastapi" in current_imports:
        # Check if an ASGI server is already present
        asgi_servers = {"uvicorn", "hypercorn", "daphne", "gunicorn"}
        has_server = any(srv in current_imports for srv in asgi_servers)
        
        if not has_server:
            # Suggest uvicorn
            additional_deps.add("uvicorn[standard]")
            
    # Flask
    if "flask" in current_imports:
        # Suggest gunicorn for prod
        # But only if not present
        if "gunicorn" not in current_imports and "uwsgi" not in current_imports:
            additional_deps.add("gunicorn")
            
    return additional_deps
