"""
templates.py
────────────
We bypass starlette's Jinja2Templates completely because newer versions of
starlette pass the template context dict as 'globals' into jinja2's
get_template(), which makes the LRU cache key unhashable (dict is not hashable).

Instead we use raw Jinja2 Environment + FileSystemLoader and return
HTMLResponse objects ourselves. This works on ALL starlette/fastapi versions.
"""
import os
from jinja2 import Environment, FileSystemLoader, select_autoescape
from fastapi.responses import HTMLResponse

_HERE = os.path.dirname(os.path.abspath(__file__))

_login_env = Environment(
    loader=FileSystemLoader(os.path.join(_HERE, "login", "templates")),
    autoescape=select_autoescape(["html"]),
)

_dashboard_env = Environment(
    loader=FileSystemLoader(os.path.join(_HERE, "dashboard", "templates")),
    autoescape=select_autoescape(["html"]),
)

_tracking_env = Environment(
    loader=FileSystemLoader(os.path.join(_HERE, "tracking", "templates")),
    autoescape=select_autoescape(["html"]),
)


_profile_env = Environment(
    loader=FileSystemLoader(os.path.join(_HERE, "profile", "templates")),
    autoescape=select_autoescape(["html"]),
)


def login_render(template_name: str, context: dict) -> HTMLResponse:
    tmpl = _login_env.get_template(template_name)
    html = tmpl.render(**context)
    return HTMLResponse(content=html)


def dashboard_render(template_name: str, context: dict) -> HTMLResponse:
    tmpl = _dashboard_env.get_template(template_name)
    html = tmpl.render(**context)
    return HTMLResponse(content=html)


def tracking_render(template_name: str, context: dict) -> HTMLResponse:
    tmpl = _tracking_env.get_template(template_name)
    html = tmpl.render(**context)
    return HTMLResponse(content=html)


def profile_render(template_name: str, context: dict) -> HTMLResponse:
    tmpl = _profile_env.get_template(template_name)
    html = tmpl.render(**context)
    return HTMLResponse(content=html)


_admin_env = Environment(
    loader=FileSystemLoader(os.path.join(_HERE, "admin", "templates")),
    autoescape=select_autoescape(["html"]),
)

def admin_render(template_name: str, context: dict) -> HTMLResponse:
    tmpl = _admin_env.get_template(template_name)
    html = tmpl.render(**context)
    return HTMLResponse(content=html)
