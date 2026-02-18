# pypm/db.py

# A curated list of popular PyPI packages commonly used in imports.
# This list is used to skip network verification for obvious packages.
# The presence of a key here means "if a user imports X, it refers to PyPI package X".

KNOWN_PYPI_PACKAGES = {
    # Data Science / ML
    "numpy", "pandas", "scipy", "matplotlib", "seaborn", "scikit-learn", 
    "tensorflow", "torch", "keras", "plotly", "bokeh", "altair", "streamlit",
    "jupyter", "notebook", "ipython", "statsmodels", "sympy", "networkx",
    
    # Web Frameworks
    "django", "flask", "fastapi", "starlette", "sanic", "tornado", "aiohttp",
    "pyramid", "bottle", "cherrypy", "falcon", "quart", "litestar",
    
    # Validation & serialization
    "pydantic", "marshmallow", "cerberus", "jsonschema", "msgspec", "orjson", "ujson",
    
    # Database / ORM
    "sqlalchemy", "tortoise-orm", "peewee", "pony", "sqlmodel", "piccolo",
    "alembic", "psycopg2", "psycopg2-binary", "asyncpg", "pymysql", "mysqlclient",
    "aiomysql", "cx_Oracle", "redis", "aioredis", "pymongo", "motor", "cassandra-driver",
    "elasticsearch", "influxdb", "clickhouse-driver",
    
    # Networking / HTTP
    "requests", "httpx", "urllib3", "aiohttp", "grequests", "uplink", "httpcore",
    
    # Utils / CLI
    "click", "typer", "rich", "tqdm", "colorama", "fire", "docopt", "argparse",
    "python-dotenv", "dynaconf", "loguru", "structlog",
    
    # Testing
    "pytest", "unittest", "nose2", "tox", "nox", "coverage", "hypothesis", "faker",
    "factory_boy", "pytest-cov", "pytest-asyncio", "pytest-mock", "pytest-xdist",
    
    # Linting / Formatting
    "black", "ruff", "isort", "mypy", "flake8", "pylint", "autopep8", "yapf",
    
    # Async
    "asyncio", "trio", "curio", "anyio", "greenlet", "gevent", "uvloop",
    
    # Security / Auth
    "passlib", "bcrypt", "argon2-cffi", "pyjwt", "python-jose", "authlib", "oauthlib",
    "cryptography", "pyopenssl",
    
    # Cloud / AWS
    "boto3", "botocore", "s3fs", "gcsfs", "azure-storage-blob", "google-cloud-storage",
    
    # Image / Vision
    "pillow", "opencv-python", "scikit-image", "moviepy", "imageio",
    
    # Report / PDF / Excel
    "reportlab", "pdfminer", "pypdf2", "pdfplumber", "weasyprint",
    "openpyxl", "xlrd", "xlsxwriter", "pandas-profiling",
    
    # DevOps / Infrastructure
    "docker", "kubernetes", "ansible", "fabric", "invoke", "pulumi", "terraform",

    # Queues
    "celery", "dramatiq", "rq", "huey",
    
    # Misc
    "pyyaml", "toml", "tomli", "xmltodict", "beautifulsoup4", "lxml", "parsel",
    "phonenumbers", "pycountry", "pytz", "pendulum", "arrow", "dateparser",
    "humanize", "bleach", "markdown",
    
    # Stdlib-like backports (often needed)
    "typing_extensions", "dataclasses", "contextvars", "mock", "enum34", "pathlib2",
    
    # User Specific (from logs)
    "email-validator", "python-multipart", "gunicorn", "uvicorn", 
    "python-barcode", "qrcode",
}
