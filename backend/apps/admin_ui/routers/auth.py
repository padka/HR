from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from backend.apps.admin_ui.security import (
    SESSION_KEY,
    Principal,
    PrincipalType,
    get_client_ip,
    limiter,
)
from backend.core.audit import AuditContext, log_audit_action
from backend.core.auth import create_access_token, verify_password
from backend.core.db import async_session
from backend.core.settings import get_settings
from backend.domain.auth_account import AuthAccount
from backend.domain.models import Recruiter

logger = logging.getLogger(__name__)


def _get_audit_context(request: Request, username: str) -> AuditContext:
    return AuditContext(
        username=username,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )


# Rate limit key function for failed login attempts - uses IP to prevent brute force
def _login_key_func(request: Request) -> str:
    return f"login:{get_client_ip(request)}"


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token")
@limiter.limit("5/minute", key_func=_login_key_func)
async def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(OAuth2PasswordRequestForm),
):
    """
    OAuth2 compatible token login, get an access token for future requests.
    """
    settings = get_settings()

    audit_ctx = _get_audit_context(request, form_data.username)

    # 1. Check against hardcoded admin credentials (if configured)
    if (
        settings.admin_username
        and form_data.username == settings.admin_username
        and form_data.password == settings.admin_password
    ):

        access_token_expires = timedelta(
            minutes=settings.state_ttl_seconds / 60
        )  # use existing TTL or default 30m
        access_token = create_access_token(
            data={"sub": form_data.username}, expires_delta=access_token_expires
        )
        await log_audit_action(
            "login_success",
            "auth",
            None,
            ctx=audit_ctx,
            changes={"method": "token", "role": "admin"},
        )
        return {"access_token": access_token, "token_type": "bearer"}

    # 2. Check against database AuthAccount
    async with async_session() as session:
        account = await session.scalar(
            select(AuthAccount).where(
                AuthAccount.username == form_data.username,
                AuthAccount.is_active.is_(True),
            )
        )
        if not account or not verify_password(
            form_data.password, account.password_hash
        ):
            await log_audit_action(
                "login_failed",
                "auth",
                None,
                ctx=audit_ctx,
                changes={"method": "token", "reason": "invalid_credentials"},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        access_token_expires = timedelta(minutes=settings.state_ttl_seconds / 60)
        access_token = create_access_token(
            data={"sub": account.username}, expires_delta=access_token_expires
        )
        await log_audit_action(
            "login_success",
            "auth",
            account.id,
            ctx=audit_ctx,
            changes={"method": "token", "role": account.principal_type},
        )
        return {"access_token": access_token, "token_type": "bearer"}


async def _resolve_principal(account: AuthAccount) -> Principal:
    p_type: PrincipalType = account.principal_type  # type: ignore[assignment]
    if p_type not in {"admin", "recruiter"}:
        raise HTTPException(status_code=400, detail="Unsupported principal type")
    return Principal(type=p_type, id=account.principal_id)


@router.post("/login")
@limiter.limit("5/minute", key_func=_login_key_func)
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    redirect_to: Optional[str] = Form("/"),
):
    audit_ctx = _get_audit_context(request, username)
    settings = get_settings()

    # Keep form login behaviour aligned with /auth/token:
    # allow configured admin credentials from environment.
    if (
        settings.admin_username
        and username == settings.admin_username
        and password == settings.admin_password
    ):
        await log_audit_action(
            "login_success",
            "auth",
            None,
            ctx=audit_ctx,
            changes={"method": "form", "role": "admin"},
        )
        request.session[SESSION_KEY] = {"type": "admin", "id": -1}
        target = redirect_to or "/"
        if not target.startswith("/") or target.startswith("//"):
            target = "/"
        return RedirectResponse(url=target, status_code=303)

    async with async_session() as session:
        account = await session.scalar(
            select(AuthAccount).where(
                AuthAccount.username == username, AuthAccount.is_active.is_(True)
            )
        )
        if not account or not verify_password(password, account.password_hash):
            await log_audit_action(
                "login_failed",
                "auth",
                None,
                ctx=audit_ctx,
                changes={"method": "form", "reason": "invalid_credentials"},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
            )
        principal = await _resolve_principal(account)
        # optional: ensure recruiter exists
        if principal.type == "recruiter":
            recruiter = await session.get(Recruiter, principal.id)
            if not recruiter:
                await log_audit_action(
                    "login_failed",
                    "auth",
                    account.id,
                    ctx=audit_ctx,
                    changes={"method": "form", "reason": "recruiter_not_found"},
                )
                raise HTTPException(status_code=401, detail="Recruiter not found")
            recruiter.last_seen_at = datetime.now(timezone.utc)
            await session.commit()

    await log_audit_action(
        "login_success",
        "auth",
        account.id,
        ctx=audit_ctx,
        changes={"method": "form", "role": principal.type},
    )
    request.session[SESSION_KEY] = {"type": principal.type, "id": principal.id}

    # Security fix: prevent open redirects
    target = redirect_to or "/"
    if not target.startswith("/") or target.startswith("//"):
        target = "/"

    return RedirectResponse(url=target, status_code=303)


@router.post("/logout")
async def logout(request: Request):
    principal_data = request.session.get(SESSION_KEY)
    username = (
        f"{principal_data.get('type', 'unknown')}:{principal_data.get('id', 'unknown')}"
        if principal_data
        else "anonymous"
    )
    await log_audit_action(
        "logout", "auth", None, ctx=_get_audit_context(request, username)
    )
    request.session.pop(SESSION_KEY, None)
    return RedirectResponse(url="/auth/login?logged_out=1", status_code=303)


@router.get("/login", response_class=HTMLResponse)
async def login_form(
    redirect_to: str = Query("/", alias="redirect_to")
) -> HTMLResponse:
    html = f"""
    <!doctype html>
    <html lang="ru">
    <head>
      <meta charset="utf-8" />
      <title>Вход | RecruitSmart</title>
      <style>
        :root {{
          --bg: #0b1220;
          --accent: #5c8bff;
          --accent-2: #6ee7ff;
          --glass: rgba(255,255,255,0.08);
          --border: rgba(255,255,255,0.14);
        }}
        * {{ box-sizing: border-box; }}
        body {{
          margin: 0;
          font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Inter, sans-serif;
          min-height: 100vh;
          display: flex;
          align-items: center;
          justify-content: center;
          background:
            radial-gradient(1200px 800px at 12% 8%, rgba(92,139,255,0.18), transparent 55%),
            radial-gradient(1100px 820px at 88% 12%, rgba(110,231,255,0.16), transparent 55%),
            radial-gradient(1400px 1000px at 50% 120%, rgba(92,139,255,0.12), transparent 60%),
            var(--bg);
          color: #e5edff;
          overflow: hidden;
        }}
        .grid {{
          position: absolute;
          inset: -40%;
          background-image: var(--grid, url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120' viewBox='0 0 120 120'%3E%3Cg fill='none' stroke='rgba(255,255,255,0.05)' stroke-width='1'%3E%3Cpath d='M60 0v120M0 60h120'/%3E%3C/g%3E%3C/svg%3E"));
          opacity: 0.45;
          filter: blur(1px);
          pointer-events: none;
        }}
        .halo {{
          position: absolute;
          inset: -30%;
          background:
            radial-gradient(40% 32% at 18% 12%, rgba(92,139,255,0.35), transparent 60%),
            radial-gradient(38% 28% at 82% 6%, rgba(110,231,255,0.28), transparent 60%);
          filter: blur(80px) saturate(1.1);
          opacity: 0.85;
          pointer-events: none;
          animation: drift 12s ease-in-out infinite alternate;
        }}
        .card {{
          position: relative;
          width: min(420px, 90vw);
          padding: 30px;
          border-radius: 18px;
          backdrop-filter: blur(24px) saturate(170%);
          -webkit-backdrop-filter: blur(24px) saturate(170%);
          background: linear-gradient(180deg, rgba(255,255,255,0.08), rgba(255,255,255,0.02));
          border: 1px solid var(--border);
          box-shadow: 0 24px 70px rgba(0,0,0,0.38), inset 0 1px 0 rgba(255,255,255,0.22);
          color: #f8fbff;
          overflow: hidden;
        }}
        .card::before {{
          content: "";
          position: absolute;
          inset: -40%;
          background: radial-gradient(60% 55% at 20% 18%, rgba(255,255,255,0.20), transparent 65%),
                      radial-gradient(70% 60% at 80% 70%, rgba(255,255,255,0.16), transparent 65%);
          filter: blur(24px);
          opacity: 0.9;
          pointer-events: none;
        }}
        .card h1 {{ margin: 0 0 6px; font-size: 24px; letter-spacing: -0.02em; }}
        .card p  {{ margin: 0 0 18px; color: #c7d2e9; font-size: 14px; }}
        .fields {{ display: flex; flex-direction: column; gap: 12px; position: relative; z-index: 1; }}
        label {{ display:block; font-weight: 600; font-size: 13px; color:#dce7ff; margin-bottom: 6px; }}
        input {{
          width: 100%;
          padding: 12px 14px;
          border-radius: 12px;
          border: 1px solid rgba(255,255,255,0.14);
          background: rgba(15,23,42,0.55);
          color: #e6eeff;
          font-size: 14px;
          outline: none;
          transition: border-color .2s ease, box-shadow .2s ease, transform .12s ease;
        }}
        input:focus {{ border-color: rgba(92,139,255,0.7); box-shadow: 0 0 0 3px rgba(92,139,255,0.24); transform: translateY(-1px); }}
        button {{
          margin-top: 16px;
          width: 100%;
          padding: 12px;
          border: none;
          border-radius: 12px;
          background: linear-gradient(120deg, #5c8bff, #6ee7ff);
          color: #06101f;
          font-weight: 800;
          font-size: 15px;
          cursor: pointer;
          box-shadow: 0 14px 36px rgba(92,139,255,0.32);
          transition: transform .14s ease, box-shadow .18s ease, filter .16s ease;
        }}
        button:hover {{ transform: translateY(-1px); filter: saturate(1.05); box-shadow: 0 18px 42px rgba(92,139,255,0.38); }}
        button:active {{ transform: translateY(1px); box-shadow: 0 10px 24px rgba(92,139,255,0.28); }}
        .logo {{
          display: inline-flex;
          align-items: center;
          gap: 10px;
          margin-bottom: 18px;
        }}
        .logo-badge {{
          width: 38px;
          height: 38px;
          border-radius: 12px;
          display: grid;
          place-items: center;
          background: linear-gradient(135deg, #5c8bff, #6ee7ff);
          color: #041022;
          font-weight: 800;
          box-shadow: 0 12px 28px rgba(92,139,255,0.35);
        }}
        .logo-text {{
          display: flex;
          flex-direction: column;
          line-height: 1.1;
        }}
        .logo-text small {{
          font-size: 11px;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          color: #9fb7e7;
        }}
        .kbd-hint {{
          display: inline-flex;
          align-items: center;
          gap: 6px;
          font-size: 12px;
          color: #c7d2e9;
          margin-top: 10px;
          opacity: 0.8;
        }}
        .kbd-hint kbd {{
          border: 1px solid rgba(255,255,255,0.16);
          border-radius: 8px;
          padding: 4px 7px;
          background: rgba(255,255,255,0.06);
          font-family: "JetBrains Mono", monospace;
          font-size: 11px;
          color: #e6eeff;
        }}
        @keyframes drift {{
          0% {{ transform: translateY(-6px) scale(1); }}
          100% {{ transform: translateY(6px) scale(1.03); }}
        }}
      </style>
    </head>
    <body>
      <div class="grid"></div>
      <div class="halo"></div>
      <form class="card" method="post" action="/auth/login">
        <div class="logo" aria-hidden="true">
          <span class="logo-badge">RS</span>
          <span class="logo-text">
            <strong>RecruitSmart</strong>
            <small>Админ панель</small>
          </span>
        </div>
        <h1>Вход</h1>
        <p>Используйте учётку admin или recruiter. Данные передаются безопасно.</p>
        <div class="fields">
          <div>
            <label for="username">Логин</label>
            <input id="username" name="username" autocomplete="username" required />
          </div>
          <div>
            <label for="password">Пароль</label>
            <input id="password" name="password" type="password" autocomplete="current-password" required />
          </div>
        </div>
        <input type="hidden" name="redirect_to" value="{redirect_to}"/>
        <button type="submit">Войти</button>
        <div class="kbd-hint" aria-hidden="true">
          <span>Совет:</span><kbd>Tab</kbd><span>для перехода по полям</span>
        </div>
      </form>
    </body>
    </html>
    """
    return HTMLResponse(content=html)
