#!/usr/bin/env python3
"""Shared token-cache / refresh helpers.

Mirrors the refresh contract used by the upstream generators we inspected:

  hot.php?status            -> cookie_expiry_ist, configured_refresh_interval_hours,
                               next_refresh_due_ist, refresh_mode
  sony_playlist.php?status  -> token_expires, ttl_hours, next_refresh, hdnea

Rule used everywhere: a playlist may only be published while every embedded
token is still valid.  Refresh is due when either

  (a) the earliest token expires within ``margin`` seconds, or
  (b) the cached copy is older than the provider's refresh interval.

That is exactly the "refresh on next request + external cron" behaviour the
upstream scripts use, except we never publish an expired token.
"""
import datetime
import json
import os
import re
import time

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
EXP_RE = re.compile(r"(?:exp|Expires)(?:=|%3D)(\d{10})")


def exp_times(text):
    """Every Akamai expiry (``hdntl=exp=...`` / ``hdnea=exp=...``) in *text*."""
    return [int(x) for x in EXP_RE.findall(text or "")]


def fmt_ist(ts):
    if not ts:
        return None
    return datetime.datetime.fromtimestamp(int(ts), IST).strftime("%d %b %Y, %I:%M:%S %p IST")


def status(text, now=None, interval_hours=None, margin=0):
    """Return the same shape of health data the upstream ``?status`` exposes."""
    now = time.time() if now is None else now
    exps = exp_times(text)
    live = [e for e in exps if e > now]
    # The binding constraint is the token that dies first.
    first = min(live) if live else (min(exps) if exps else 0)
    data = {
        "tokens": len(exps),
        "live": len(live),
        "token_expires": fmt_ist(first),
        "token_expires_epoch": first or None,
        "expires_in_hours": round((first - now) / 3600, 2) if first else None,
        "stale": (not exps) or first <= now + margin,
    }
    if interval_hours:
        data["configured_refresh_interval_hours"] = interval_hours
        data["next_refresh"] = fmt_ist(now + interval_hours * 3600)
    return data


def is_fresh(text, margin=1800, now=None):
    """True only if *text* carries at least one token and none is near expiry."""
    now = time.time() if now is None else now
    exps = exp_times(text)
    return bool(exps) and min(exps) > now + margin


def refresh_due(state, interval_hours, margin, now=None):
    """Cached-state equivalent of the upstream age/expiry check."""
    now = time.time() if now is None else now
    if not state:
        return True
    exp = int(state.get("token_expires_epoch") or 0)
    if exp and exp <= now + margin:
        return True
    fetched = int(state.get("fetched_at") or 0)
    return (now - fetched) >= interval_hours * 3600


def load_state(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(path, state):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1, sort_keys=True)
    os.replace(tmp, path)
