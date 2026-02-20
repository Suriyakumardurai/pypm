# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.0.6   | :white_check_mark: |
| 0.0.5   | :white_check_mark: |
| < 0.0.5 | :x:                |

## Python Version Support

pypm 0.0.6 supports Python 3.5 through 3.14:

| Python Version | Support Level |
|---|---|
| 3.5 – 3.7 | Compatible (**vermin** verified) |
| 3.8 – 3.14 | Fully supported (CI tested) |

## Security Measures

pypm 0.0.5 includes the following built-in security protections:

### Command Injection Prevention
All package names are validated against a PEP 508-compliant regex and checked for shell metacharacters (`; & | \` $ ( ) { }` etc.) before being passed to `pip` or `uv`. Malicious names are rejected and logged.

### URL Sanitization
Import names are validated and sanitized before being used in PyPI API URLs (`https://pypi.org/pypi/<name>/json`). Path traversal attempts (`..`), URL-unsafe characters (`/ ? # & =`), and names longer than 200 characters are rejected.

### Cache Hardening
- The disk cache at `~/.cache/pypm/cache.json` uses restrictive file permissions (`600` on Unix) — owner read/write only.
- Cache entries are validated on load. Corrupt or invalid entries are silently dropped.
- JSON parse errors reset the cache instead of crashing.

### Symlink Protection
Symlinked directories and files are skipped during scanning to prevent infinite loops and directory traversal attacks.

### Resource Limits
- Files larger than 10MB are skipped to prevent memory exhaustion.
- PyPI API responses larger than 5MB are rejected.

## Reporting a Vulnerability

We take the security of pypm seriously. If you believe you have found a security vulnerability in pypm, please report it to us as described below.

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please report them via email to [suriyakumardurai.sk.in@gmail.com](mailto:suriyakumardurai.sk.in@gmail.com).

You should receive a response within 48 hours. If for some reason you do not, please follow up via email to ensure we received your original message.
