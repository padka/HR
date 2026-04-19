# Live Contour Incident Recovery

## Purpose

Этот runbook покрывает два live-контура:

- `admin` -> `recruitsmart-admin.service`
- `maxpilot` -> `recruitsmart-maxpilot-admin-api.service`

Цель: не рестартовать сервис после частичного копирования файлов и не повторять crash loop вида `ModuleNotFoundError`/`ImportError` уже после live-deploy.

## Canonical Manifests

- `deploy/contours/admin.txt`
- `deploy/contours/maxpilot.txt`

Их нужно использовать как минимальный bounded package для deploy, а не копировать отдельные Python-файлы вручную.

## Required Preflight

Перед любым restart на контуре выполнить:

```bash
python scripts/contour_preflight.py --contour admin --root /opt/recruitsmart_admin
python scripts/contour_preflight.py --contour maxpilot --root /opt/recruitsmart_maxpilot
```

Preflight обязан проверить:

- все пути из contour manifest присутствуют;
- expected migration revision существует в `backend/migrations/versions`;
- ключевые runtime imports проходят без `ModuleNotFoundError` и `ImportError`.

Если preflight красный, сервис не рестартовать.

## Recovery Order

1. Сделать backup текущего контура.
2. Залить полный bounded package по manifest.
3. Выполнить `python -m py_compile` на ключевых runtime файлах контура.
4. Выполнить `python scripts/contour_preflight.py ...`.
5. Только после зелёного preflight делать `systemctl restart ...`.
6. Проверить:
   - `systemctl status <service>`
   - `journalctl -u <service> -n 100 --no-pager`
   - внешний `/health`
   - ключевой smoke (`/admin` или `/miniapp`)

## Rollback

Если preflight зелёный, но сервис после restart упал:

1. восстановить backup контура;
2. повторить preflight на восстановленном наборе;
3. перезапустить сервис;
4. записать root cause в execution log.

## Incident Notes

- `admin` contour не должен падать из-за bounded MAX pilot модулей. MAX rollout и dual-write imports должны быть lazy или приходить вместе с полным manifest package.
- `maxpilot` contour считается MAX-only surface. `/miniapp` должен открываться только внутри MAX, а browser open обязан fail-close без bootstrap запроса.
