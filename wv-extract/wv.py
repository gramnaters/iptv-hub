#!/usr/bin/env python3
"""
wv.py — self-made Widevine content-key extractor.

Turns a WVD (Widevine Device: client_id + RSA private key) into real content
keys the same way a licensed CDM does: open a session, hand the license server a
signed challenge, and decrypt the keys out of the licence response.

This is the "get the key with a WVD private key" step — the exact mechanism the
upstream playlists used to mint the static ClearKeys they publish. It is service
agnostic: give it a PSSH and a license URL and it returns KID:KEY pairs.

Flow
  1. load a .wvd device
  2. cdm.open() -> session
  3. (optional) install the service certificate
  4. cdm.get_license_challenge(session, pssh) -> signed protobuf
  5. POST the challenge to license_url (with caller-provided headers)
  6. cdm.parse_license(session, response)
  7. read cdm.get_keys(session) -> {kid: key}

It walks every .wvd in the pool so one revoked/limited device never blocks the
job — the first device that yields keys wins.

Usage
  CLI:
    python wv.py --pssh <b64|hex> --license <url> [--headers file.json]
                 [--wvd device.wvd | --wvd-dir D:/JioTV/wvd]
                 [--cert <b64|hex|url>] [--json]

  Import:
    from wv import extract, KeyError as WVError
    keys = extract(pssh, license_url, headers={...})
    # keys -> {"089f6cf0...": "35d3a0a1..."}
"""

from __future__ import annotations

import base64
import glob
import json
import os
import re
import sys

import requests
from pywidevine.cdm import Cdm
from pywidevine.device import Device
from pywidevine.pssh import PSSH

try:
    from pywidevine.exceptions import InvalidSession
except Exception:  # pragma: no cover - older pywidevine
    InvalidSession = Exception

DEFAULT_WVD_DIR = os.environ.get("WVD_DIR") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "wvd")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


class WVError(Exception):
    """Raised when no device in the pool can produce keys."""


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _to_bytes(value) -> bytes:
    """Accept bytes, base64, or hex and return raw bytes."""
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        s = value.strip()
        if re.fullmatch(r"[0-9a-fA-F]+", s) and len(s) % 2 == 0 and len(s) >= 32:
            return bytes.fromhex(s)
        try:
            return base64.b64decode(s, validate=True)
        except Exception:
            # urlsafe or unpadded base64
            pad = "=" * (-len(s) % 4)
            return base64.b64decode(s.replace("-", "+").replace("_", "/") + pad)
    raise TypeError("expected bytes, base64 or hex string")


def _load_devices(wvd: str | None, wvd_dir: str) -> list[str]:
    if wvd:
        return [wvd]
    return sorted(glob.glob(os.path.join(wvd_dir, "*.wvd")))


def _header_dict(headers) -> dict:
    if not headers:
        return {}
    if isinstance(headers, dict):
        return dict(headers)
    if isinstance(headers, str) and os.path.isfile(headers):
        with open(headers, "r", encoding="utf-8") as fh:
            return json.load(fh)
    if isinstance(headers, str):
        try:
            return json.loads(headers)
        except json.JSONDecodeError:
            return {}
    return {}


def _cert_bytes(cert) -> bytes | None:
    if cert is None:
        return None
    if isinstance(cert, bytes):
        return cert
    s = cert.strip()
    if re.fullmatch(r"https?://[^\s]+", s):
        r = requests.get(s, headers={"User-Agent": UA}, timeout=30)
        r.raise_for_status()
        return r.content
    return _to_bytes(s)


# --------------------------------------------------------------------------- #
# core
# --------------------------------------------------------------------------- #

def extract(
    pssh: str | bytes,
    license_url: str,
    headers: dict | str | None = None,
    wvd: str | None = None,
    wvd_dir: str = DEFAULT_WVD_DIR,
    cert=None,
    timeout: int = 30,
    licence_type: str = "STREAMING",
) -> dict[str, str]:
    """Extract content keys. Returns {kid_hex: key_hex}. Raises WVError."""
    pssh_obj = PSSH(_to_bytes(pssh))
    header_map = _header_dict(headers)
    header_map.setdefault("User-Agent", UA)
    cert = _cert_bytes(cert)

    devices = _load_devices(wvd, wvd_dir)
    if not devices:
        raise WVError(f"no .wvd files found in {wvd_dir}")

    last_err = None
    for dev_path in devices:
        name = os.path.basename(dev_path)
        cdm = None
        try:
            device = Device.load(dev_path)
            cdm = Cdm.from_device(device)
            session = cdm.open()

            if cert is not None:
                cdm.set_service_certificate(session, cert)

            challenge = cdm.get_license_challenge(
                session, pssh_obj, licence_type
            )

            resp = requests.post(
                license_url,
                data=challenge,
                headers=header_map,
                timeout=timeout,
            )
            if resp.status_code not in (200, 201):
                raise WVError(f"{name}: license server HTTP {resp.status_code}")

            cdm.parse_license(session, resp.content)
            keys = {
                k.kid.hex.lower(): k.key.hex()
                for k in cdm.get_keys(session)
                if k.type == "CONTENT"
            }
            if keys:
                cdm.close(session)
                return keys
            last_err = f"{name}: no CONTENT keys in licence"
        except Exception as e:  # noqa: BLE001 - try the next device
            last_err = f"{name}: {e}"
        finally:
            if cdm is not None:
                try:
                    cdm.close(session)
                except Exception:
                    pass

    raise WVError(f"all {len(devices)} devices failed (last: {last_err})")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _main(argv: list[str]) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Widevine content-key extractor (WVD)")
    ap.add_argument("--pssh", required=True, help="PSSH as base64 or hex")
    ap.add_argument("--license", required=True, help="Widevine license server URL")
    ap.add_argument("--headers", help="JSON file or JSON string of request headers")
    ap.add_argument("--wvd", help="single .wvd file (default: scan --wvd-dir)")
    ap.add_argument("--wvd-dir", default=DEFAULT_WVD_DIR, help="directory of .wvd files")
    ap.add_argument("--cert", help="service certificate: b64 | hex | URL")
    ap.add_argument("--licence-type", default="STREAMING")
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--json", action="store_true", help="emit JSON")

    args = ap.parse_args(argv)

    try:
        keys = extract(
            args.pssh,
            args.license,
            headers=args.headers,
            wvd=args.wvd,
            wvd_dir=args.wvd_dir,
            cert=args.cert,
            timeout=args.timeout,
            licence_type=args.licence_type,
        )
    except WVError as e:
        print(f"[-] {e}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"[-] {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(keys, indent=2))
    else:
        for kid, key in keys.items():
            print(f"{kid}:{key}")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
