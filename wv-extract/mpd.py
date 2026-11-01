#!/usr/bin/env python3
"""
mpd.py — pull Widevine DRM metadata out of a DASH manifest.

A DASH manifest carries everything a player needs to start the license dance
except (usually) the license URL, which the app supplies out-of-band. This
extracts the two things that ARE in the manifest:

  * the Widevine PSSH (base64, system id edef8ba9-79d6-4ace-a3c8-27dcd51d21ed)
  * the default KID (cenc:default_KID), normalised to hex

and the license URL where present (Laurl / ms:laurl / dashif:laurl).
"""

from __future__ import annotations

import base64
import re
import xml.etree.ElementTree as ET

WIDEVINE_UUID = "edef8ba9-79d6-4ace-a3c8-27dcd51d21ed"

_CENC = "{urn:mpeg:cenc:2013}"


def _ns_clean(elem: ET.Element) -> None:
    """Strip namespaces so we can match tags by local name."""
    for el in elem.iter():
        if "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]


def parse_mpd(text: str) -> dict:
    """Parse a DASH MPD and return {pssh, kid, license_url, pssh_period}."""
    out = {"pssh": "", "kid": "", "license_url": "", "pssh_raw": None}

    root = ET.fromstring(text)
    _ns_clean(root)

    # 1) Widevine PSSH
    for cp in root.iter("ContentProtection"):
        uri = (cp.get("schemeIdUri") or "").lower()
        if WIDEVINE_UUID in uri:
            pssh_el = cp.find("pssh")
            if pssh_el is not None and pssh_el.text:
                out["pssh_raw"] = pssh_el.text.strip()
                out["pssh"] = pssh_el.text.strip()

    # fallback: any cenc:pssh with a Widevine-looking box header
    if not out["pssh"]:
        for p in root.iter("pssh"):
            raw = (p.text or "").strip()
            if raw:
                try:
                    head = base64.b64decode(raw)
                    if head[12:28] == bytes.fromhex(WIDEVINE_UUID.replace("-", "")):
                        out["pssh"] = raw
                        out["pssh_raw"] = raw
                        break
                except Exception:
                    continue

    # 2) default KID (search by attribute name across namespaces)
    for el in root.iter():
        for attr, val in el.attrib.items():
            if attr.endswith("default_KID") and val:
                out["kid"] = re.sub(r"[^0-9a-fA-F]", "", val).lower()
                break
        if out["kid"]:
            break

    # 3) license URL from any laurl element
    for el in root.iter():
        if el.tag.lower().endswith("laurl"):
            for attr in ("licenseUrl", "Licensing", "url", "license_url"):
                if el.get(attr):
                    out["license_url"] = el.get(attr)
                    break
        if out["license_url"]:
            break

    return out
