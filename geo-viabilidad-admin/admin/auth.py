"""Autenticación de sesión para el panel admin."""

from __future__ import annotations

import hmac
from functools import wraps

from flask import flash, redirect, session, url_for

from admin.config import AdminConfig


def verify_admin_credentials(username: str, password: str) -> bool:
    user_ok = hmac.compare_digest(username.strip(), AdminConfig.ADMIN_USERNAME)
    pass_ok = hmac.compare_digest(password, AdminConfig.ADMIN_PASSWORD)
    return user_ok and pass_ok


def login_admin(username: str) -> None:
    session.clear()
    session["admin_user"] = username.strip()
    session.permanent = True


def logout_admin() -> None:
    session.clear()


def is_admin_logged_in() -> bool:
    return bool(session.get("admin_user"))


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not is_admin_logged_in():
            flash("Inicia sesión para acceder al panel administrativo.", "warning")
            return redirect(url_for("admin.login"))
        return view(*args, **kwargs)

    return wrapped
