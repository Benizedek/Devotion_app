"""Collects every feature's ROUTES into one table and finds the handler for a request.

Each module in app/api/ declares its own ROUTES list of (method, path pattern, handler, login required).
To add an endpoint: write the handler in the right module and add a row to that module's ROUTES.
"""
import re

from .api import accounts, chats, devotions, messages, people, prayers, sharing

FEATURES = [accounts, chats, messages, sharing, devotions, prayers, people]

ROUTES = [(method, re.compile(pattern + "$"), handler, needs_login)
          for feature in FEATURES
          for method, pattern, handler, needs_login in feature.ROUTES]


def find(method: str, path: str):
    """Return (handler, needs_login, url_args) or None if no route matches."""
    for route_method, pattern, handler, needs_login in ROUTES:
        match = pattern.match(path)
        if match and route_method == method:
            return handler, needs_login, match.groups()
    return None
