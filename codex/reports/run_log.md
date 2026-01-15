# Dry-run log — 2025-10-18

## Python dependency install
```bash
$ pip install -e ".[dev]"
Successfully installed ... uvicorn-0.30.6 watchfiles-1.1.1 websockets-15.0.1
```

## FastAPI startup attempts
```bash
$ python -m uvicorn backend.apps.admin_ui.app:app --host 127.0.0.1 --port 8000
ModuleNotFoundError: No module named 'aiohttp'
```

```bash
$ timeout 5 python -m uvicorn backend.apps.admin_ui.app:app --host 127.0.0.1 --port 8000
RuntimeError: Invalid sensitive configuration detected:
 - ADMIN_USER must be defined and use a non-default value
 - ADMIN_PASSWORD must be defined and use a non-default value
```

```bash
$ ADMIN_USER=codex ADMIN_PASSWORD=codex SESSION_SECRET_KEY=supersecretsecretsecretsecretsecret \
  timeout 5 python -m uvicorn backend.apps.admin_ui.app:app --host 127.0.0.1 --port 8000
INFO:     Application startup complete.
INFO:     Finished server process
```

## Asset build
```bash
$ npm run build
> hr-admin-ui@0.1.0 build
> npm run build:css
Browserslist: caniuse-lite is outdated...
Done in 1230ms.
```

## Test suite
```bash
$ pytest -q
...
E           RuntimeError: There is no current event loop in thread 'MainThread'.
...
FAILED tests/test_ui_screenshots.py::test_ui_screenshots - playwright._impl._errors.Error: BrowserType.launch: Executable doesn't exist
69 failed, 42 passed, 5 warnings in 23.97s
```

## Health probe
```bash
$ curl -i http://127.0.0.1:8000/health
HTTP/1.1 200 OK
{"status":"ok","checks":{"database":"ok","state_manager":"ok","bot_client":"unconfigured","bot_integration":"enabled","bot":"unconfigured"}}
```
