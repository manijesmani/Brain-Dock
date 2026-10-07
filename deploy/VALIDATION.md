# Release validation

Local review completed on 2026-10-07. This is a validation record, not a
confirmation that the production server has been updated.

## Local checks

The available environment is Windows, Node.js 24.19.0 and Python 3.12.
Production/CI target Node.js 22 and Python 3.13.

| Check | Result |
| --- | --- |
| Frontend TypeScript and Vite production build | Passed after reinstalling locked dependencies |
| Frontend ESLint and Prettier | Passed |
| Backend and deployment Ruff lint/format | Passed |
| Backend tests without `django_db` | 51 passed; 505 database tests deselected |
| Deployment safety tests | 9 passed; 1 POSIX-permissions test skipped on Windows |
| Django production `check --deploy --fail-level WARNING` | Passed with disposable configuration |

The frontend build reports a bundle-size warning: the main JavaScript asset
is approximately 1.09 MB, or 318 KB compressed. This does not fail the build.

## Fixes found during validation

- Source packaging now works on Windows without importing Linux-only `fcntl`.
- Deployment commands report that they require Linux before changing settings
  on Windows.
- Release packages give shell scripts executable permissions and LF endings,
  even when the source checkout is on Windows.
- Media archive path checks use POSIX archive paths consistently across hosts.
- Git attributes keep shell scripts in LF format.

## Required before production approval

Run the full CI workflow on Linux with PostgreSQL 17, ffmpeg and Docker:

```sh
cd backend
pytest
cd ..
python3 -m unittest discover -s deploy/tests -v
python3 -u deploy/verify.py
```

The local machine has no Docker installation or PostgreSQL service. The EDB
PostgreSQL binary download returned an HTTP 403 regional restriction. The
full database suite, POSIX permission check and Docker deployment/restore
verification therefore remain unverified locally.

Live Telegram delivery and the production server require their actual
configuration and were not exercised by this review.
