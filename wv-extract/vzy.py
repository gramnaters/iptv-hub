#!/usr/bin/env python3
"""
vzy.py — VZY / Dish TV live-channel key extraction (Widevine, Nagra SSP).

REVERSED from the VZY app (com.vzy.one v1.0.78). Dish TV's OTT stack is a Kaltura
+ Nagra SSP build (the "com.horizon.kstream" / Watcho codebase). The full DRM
flow, extracted from the decompiled APK:

  1. content-auth-token
       POST https://vzy-sso.dish.watcho.com/v1/content-auth-token
       headers: x-api-key: OtQoJFYdAy8H8fOARcvXS39GtcvjCfEF8ZGJujRw
                x-partner-name: Nagra
       body (DrmAuthRequest):
         accountId:      <userId or random device id>
         contentId:      <channel mediaExternalId (Kaltura entry id)>
         type:           "0"              (KALTURA_PRODUCT_ID_MONTHLY_INDIA)
         deviceUniqueId: "34"
         deviceId:       <random device id>
         format:         "widevine"
         platform:       "android"
       -> { token (JWT), licenseUrl, certificateUrl }

  2. service certificate
       GET https://<tenant>.anycast.nagra.com/<tenant>/wvls/contentlicenseservice/v1/certificates

  3. license
       POST https://<tenant>.anycast.nagra.com/<tenant>/wvls/contentlicenseservice/v1/licenses
       headers: nv-authorizations: <token JWT>
       body:    CDM license challenge
       -> license -> content keys

Dish's Nagra tenant is **DSHP4R35**, so the license URL is:

  https://dshp4r35.anycast.nagra.com/DSHP4R35/wvls/contentlicenseservice/v1/licenses

The token mint is VERIFIED working (200). The license POST body is the plain
Widevine **protobuf** SignedMessage (NOT ASN.1 DER) with
`Content-Type: application/octet-stream` and the `nv-authorizations: <token>`
header — confirmed by decompiling the VZY APK (com.vzy.one): the app uses
Kaltura PlayKit's `HttpMediaDrmCallback`, which POSTs `MediaDrm.getKeyRequest()`
(protobuf) directly. No service certificate / privacy mode is used in the
streaming path (only token + licenseUrl are consumed from the auth response).

The Nagra OpenAPI `MIIEmo...` example is the *internal* SSP<->license-server DER
format, not what the player sends. Sending DER (or applying the cert) makes Nagra
return `400 errorCode 2001 "Invalid challenge format"`. The correct plaintext
protobuf challenge is accepted.

The remaining piece was the *contentId*: the content-auth-token needs the Kaltura
asset's **externalId** (e.g. ``HE_E_10100`` for &Pictures HD), NOT the numeric
``assetId`` (``9487112``). The numeric id yields ``errorCode 4011`` ("No valid key
found for the Key id"). With the externalId the license returns the content key.
"""

from __future__ import annotations

import json
import os
import sys
import uuid

import requests
from pywidevine.pssh import PSSH

from mpd import parse_mpd
from wv import extract as wv_extract

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36")

WIDEVINE_UUID = "edef8ba9-79d6-4ace-a3c8-27dcd51d21ed"

# ---- Dish VZY DRM secrets (from the decompiled APK) ------------------------ #
DRM_API_KEY = "OtQoJFYdAy8H8fOARcvXS39GtcvjCfEF8ZGJujRw"
DRM_HOST = "https://vzy-sso.dish.watcho.com"
NAGRA_TENANT = "DSHP4R35"
LICENSE_URL = f"https://{NAGRA_TENANT.lower()}.anycast.nagra.com/{NAGRA_TENANT}/wvls/contentlicenseservice/v1/licenses"
CERT_URL = f"https://{NAGRA_TENANT.lower()}.anycast.nagra.com/{NAGRA_TENANT}/wvls/contentlicenseservice/v1/certificates"


def content_auth_token(content_id: str) -> dict:
    """Mint the Nagra content-auth token. Returns {token, license_url, cert_url}."""
    dev = str(uuid.uuid4())
    r = requests.post(
        f"{DRM_HOST}/v1/content-auth-token",
        headers={"x-api-key": DRM_API_KEY, "x-partner-name": "Nagra",
                 "Content-Type": "application/json"},
        json={
            "accountId": dev,
            "contentId": content_id,
            "type": "0",
            "deviceUniqueId": "34",
            "deviceId": dev,
            "format": "widevine",
            "platform": "android",
        },
        timeout=20,
    )
    r.raise_for_status()
    d = r.json()
    return {
        "token": d["token"],
        "license_url": d.get("licenseUrl") or LICENSE_URL,
        "cert_url": d.get("certificateUrl") or CERT_URL,
    }


def service_certificate(auth: dict) -> bytes:
    return requests.get(
        CERT_URL, headers={"nv-authorizations": auth["token"]}, timeout=20
    ).content


# ---- Kaltura asset lookup (maps a numeric assetId -> Nagra externalId) ----- #
KALTURA_BASE = "https://5093.dsp1.ott.kaltura.com/api_v3"
KALTURA_PARTNER_ID = 5093
KALTURA_API_VERSION = "11.2.0.1"
KALTURA_CLIENT_TAG = "KSPAND-1.0.3(100)"


def kaltura_session() -> str:
    """Anonymous Kaltura login -> ks (session token)."""
    r = requests.post(
        f"{KALTURA_BASE}/service/ottuser/action/anonymouslogin",
        headers={"User-Agent": UA, "Accept": "application/json",
                 "Content-Type": "application/json"},
        json={"apiVersion": KALTURA_API_VERSION, "clientTag": KALTURA_CLIENT_TAG,
              "partnerId": KALTURA_PARTNER_ID},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()["result"]["ks"]


def kaltura_external_id(asset_id) -> str:
    """Map a numeric Kaltura assetId to its Nagra externalId (the DRM contentId).

    The content-auth-token wants the asset's *externalId* (e.g. ``HE_E_10100`` for
    &Pictures HD), NOT the numeric assetId (``9487112``). Sending the assetId makes
    Nagra return ``errorCode 4011`` ("No valid key found for the Key id").
    """
    ks = kaltura_session()
    r = requests.post(
        f"{KALTURA_BASE}/service/asset/action/get",
        headers={"User-Agent": UA, "Accept": "application/json",
                 "Content-Type": "application/json"},
        json={"apiVersion": KALTURA_API_VERSION, "ks": ks, "id": str(asset_id),
              "assetReferenceType": "media", "language": "*",
              "ClientTag": KALTURA_CLIENT_TAG},
        timeout=20,
    )
    r.raise_for_status()
    res = r.json().get("result", {})
    if "error" in res:
        raise RuntimeError(f"Kaltura asset {asset_id}: {res['error'].get('message')}")
    return res.get("externalId") or ""


def pssh_from_kid(kid: str) -> str:
    """Build a Widevine PSSH (base64) from a bare KID hex (Broadpeak MPDs have no PSSH)."""
    kid = kid.replace("-", "").lower()
    return PSSH.new(system_id=uuid.UUID(WIDEVINE_UUID),
                    key_ids=[bytes.fromhex(kid)], version=1).dumps()


def get_keys(mpd_url: str, content_id: str | None = None,
             asset_id: str | None = None, wvd_dir: str | None = None) -> dict:
    """Extract the content key for a VZY/Dish DASH manifest. Returns {kid: key}.

    ``content_id`` is the Nagra externalId (e.g. ``HE_E_10100``). If you only have
    the numeric Kaltura ``asset_id`` (the tvg-id), pass it instead and the externalId
    is resolved via the Kaltura API.
    """
    mpd = requests.get(mpd_url, headers={"User-Agent": UA}, timeout=20).text
    meta = parse_mpd(mpd)

    pssh = meta["pssh"]
    if not pssh and meta["kid"]:
        pssh = pssh_from_kid(meta["kid"])
    if not pssh:
        raise RuntimeError(f"no PSSH and no KID in {mpd_url}")

    # contentId = the asset's externalId (HE_E_...), NOT the numeric assetId.
    cid = content_id or (kaltura_external_id(asset_id) if asset_id else None)
    if not cid:
        raise RuntimeError("no content_id / asset_id given")
    auth = content_auth_token(cid)

    kwargs = {
        "headers": {
            "nv-authorizations": auth["token"],
            "Content-Type": "application/octet-stream",
        },
    }
    if wvd_dir:
        kwargs["wvd_dir"] = wvd_dir
    return wv_extract(pssh, auth["license_url"], **kwargs)


def _main(argv: list[str]) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="VZY / Dish TV Widevine key extractor")
    ap.add_argument("mpd_url", help="DASH manifest URL")
    ap.add_argument("--content-id", default=None,
                    help="Nagra externalId (e.g. HE_E_10100)")
    ap.add_argument("--asset-id", default=None,
                    help="numeric Kaltura assetId / tvg-id (externalId is auto-resolved)")
    ap.add_argument("--wvd-dir", default=None, help="directory of .wvd files")
    ap.add_argument("--json", action="store_true")

    args = ap.parse_args(argv)

    try:
        keys = get_keys(args.mpd_url, args.content_id, args.asset_id, args.wvd_dir)
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
