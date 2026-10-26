#!/usr/bin/env python3
"""
JioTV mobile authentication module.
"""
import os
import sys
import json
import base64
import time
import requests

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

API = "https://jiotvapi.media.jio.com"
APPKEY = "NzNiMDhlYzQyNjJm"
VERSION_CODE = "422"
USER_AGENT_OKHTTP = "okhttp/4.12.0"
DEVICE_ID_DEFAULT = "3c6d6b5702fa09bd"

BASE_HEADERS = {
    "appkey": APPKEY,
    "devicetype": "phone",
    "os": "android",
    "versionCode": VERSION_CODE,
    "User-Agent": USER_AGENT_OKHTTP,
    "lbcookie": "1",
    "usertype": "JIO",
    "usergroup": "tvYR7NSNn7rymo3F",
    "languageId": "6",
    "isott": "false",
}


def b64(s: str) -> str:
    return base64.b64encode(s.encode("utf-8")).decode("utf-8")


def send_otp(mobile: str) -> dict:
    clean = mobile.strip().replace("+91", "").replace(" ", "")
    payload = {"number": b64("+91" + clean)}
    headers = {
        "appname": "RJIL_JioTV",
        "os": "android",
        "devicetype": "phone",
        "User-Agent": USER_AGENT_OKHTTP,
        "Content-Type": "application/json",
    }
    try:
        r = requests.post(f"{API}/userservice/apis/v1/loginotp/send",
                          json=payload, headers=headers, timeout=15)
        return {"ok": r.status_code in (200, 204), "status": r.status_code, "body": r.text}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def verify_otp(mobile: str, otp: str, device_id: str = DEVICE_ID_DEFAULT) -> dict:
    clean = mobile.strip().replace("+91", "").replace(" ", "")
    payload = {
        "number": b64("+91" + clean),
        "otp": otp.strip(),
        "deviceInfo": {
            "consumptionDeviceName": "SM-G930F",
            "info": {
                "type": "android",
                "platform": {"name": "SM-G930F"},
                "androidId": device_id,
            },
        },
    }
    headers = {
        "appname": "RJIL_JioTV",
        "os": "android",
        "devicetype": "phone",
        "User-Agent": USER_AGENT_OKHTTP,
        "Content-Type": "application/json",
    }
    try:
        r = requests.post(f"{API}/userservice/apis/v1/loginotp/verify",
                          json=payload, headers=headers, timeout=15)
        d = r.json()
        if d.get("authToken"):
            user = d.get("sessionAttributes", {}).get("user", {})
            creds = {
                "ssoToken": d.get("ssoToken"),
                "authToken": d.get("authToken"),
                "refreshToken": d.get("refreshToken"),
                "deviceId": device_id,
                "subscriberId": user.get("subscriberId"),
                "uniqueId": user.get("unique"),
            }
            return {"ok": True, "creds": creds}
        return {"ok": False, "message": d.get("message", "verification failed"), "raw": d}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def refresh_access_token(creds: dict) -> dict:
    """Refresh authToken using refreshToken (current JioTV v422 profile)."""
    refresh_tok = creds.get("refreshToken")
    if not refresh_tok:
        return {"ok": False, "message": "no refreshToken"}
    payload = {
        "appName": "RJIL_JioTV",
        "deviceId": creds.get("deviceId", DEVICE_ID_DEFAULT),
        "refreshToken": refresh_tok,
    }
    headers = {
        "devicetype": "phone",
        "versionCode": VERSION_CODE,
        "os": "android",
        "Content-Type": "application/json; charset=utf-8",
        "Host": "auth.media.jio.com",
        "User-Agent": USER_AGENT_OKHTTP,
        "accessToken": creds.get("authToken", ""),
    }
    try:
        r = requests.post("https://auth.media.jio.com/tokenservice/apis/v1/refreshtoken?langId=6",
                          json=payload, headers=headers, timeout=15)
        d = r.json()
        if d.get("authToken"):
            creds["authToken"] = d["authToken"]
            return {"ok": True, "authToken": d["authToken"]}
        return {"ok": False, "message": d.get("message", "refresh failed"), "raw": d}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def refresh_sso_token(creds: dict) -> dict:
    """Refresh ssoToken via tv.media.jio.com (current JioTV v422 profile)."""
    sso = creds.get("ssoToken")
    unique = creds.get("uniqueId")
    device = creds.get("deviceId", DEVICE_ID_DEFAULT)
    if not sso or not unique:
        return {"ok": False, "message": "missing ssoToken/uniqueId"}
    headers = {
        "devicetype": "phone",
        "versionCode": VERSION_CODE,
        "os": "android",
        "Host": "tv.media.jio.com",
        "User-Agent": USER_AGENT_OKHTTP,
        "ssoToken": sso,
        "uniqueid": unique,
        "deviceid": device,
    }
    try:
        r = requests.get("https://tv.media.jio.com/apis/v2.0/loginotp/refresh?langId=6",
                         headers=headers, timeout=15)
        d = r.json()
        if d.get("ssoToken"):
            creds["ssoToken"] = d["ssoToken"]
            return {"ok": True, "ssoToken": d["ssoToken"]}
        return {"ok": False, "message": "no ssoToken in response", "raw": d}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def ensure_fresh(creds: dict) -> dict:
    """Refresh authToken (and ssoToken) if needed; returns the working creds."""
    if creds.get("authToken"):
        r = refresh_access_token(creds)
        if r.get("ok"):
            return creds
    if creds.get("ssoToken"):
        refresh_sso_token(creds)
    return creds


def auth_headers(creds: dict) -> dict:
    """Authenticated headers for channel-list + geturl calls."""
    h = dict(BASE_HEADERS)
    if creds.get("authToken"):
        h["accessToken"] = creds["authToken"]
    if creds.get("ssoToken"):
        h["ssotoken"] = creds["ssoToken"]
    if creds.get("subscriberId"):
        h["crmid"] = creds["subscriberId"]
        h["subscriberId"] = creds["subscriberId"]
        h["userId"] = creds["subscriberId"]
    if creds.get("uniqueId"):
        h["uniqueId"] = creds["uniqueId"]
    return h


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python jio_auth.py send <mobile>")
        print("  python jio_auth.py verify <mobile> <otp> [deviceId]")
        sys.exit(1)
    cmd = sys.argv[1].lower()
    if cmd == "send":
        print(send_otp(sys.argv[2]))
    elif cmd == "verify":
        mobile = sys.argv[2]
        otp = sys.argv[3]
        device = sys.argv[4] if len(sys.argv) > 4 else DEVICE_ID_DEFAULT
        res = verify_otp(mobile, otp, device)
        if res.get("ok"):
            out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "jiotv_creds.json")
            with open(out, "w", encoding="utf-8") as f:
                json.dump(res["creds"], f, indent=2)
            print("saved to", out)
        print(res)
