#!/usr/bin/env python3
"""
jio_auth.py — JioTV Authentication and Token Manager.
Handles session verification, token auto-refresh, and live stream token minting.
"""
import os
import sys
import json
import base64
import re
import time
import requests

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

COMMON_HEADERS = {
    "devicetype": "phone",
    "appname": "RJIL_JioTV",
    "os": "android",
    "User-Agent": "okhttp/4.2.2",
    "Accept-Encoding": "gzip",
}

def b64_encode(s: str) -> str:
    return base64.b64encode(s.encode("utf-8")).decode("utf-8")

def send_otp(mobile: str) -> dict:
    """Send OTP to the given 10-digit Indian mobile number."""
    clean_mobile = mobile.strip().replace("+91", "").replace(" ", "")
    payload = {"number": b64_encode("+91" + clean_mobile)}
    headers = {**COMMON_HEADERS, "Content-Type": "application/json"}
    
    url = "https://jiotvapi.media.jio.com/userservice/apis/v1/loginotp/send"
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        return {
            "status_code": resp.status_code,
            "success": resp.status_code == 200 or resp.status_code == 204,
            "body": resp.text
        }
    except Exception as e:
        return {"status_code": 0, "success": False, "error": str(e)}

def verify_otp(mobile: str, otp: str) -> dict:
    """Verify OTP and return persistent session credentials."""
    clean_mobile = mobile.strip().replace("+91", "").replace(" ", "")
    clean_otp = otp.strip()
    
    payload = {
        "number": b64_encode("+91" + clean_mobile),
        "otp": clean_otp,
        "deviceInfo": {
            "consumptionDeviceName": "SM-G935FD",
            "info": {
                "platform": {"name": "SM-G935FD"},
                "androidId": "3c6d6b5702fa09bd",
                "type": "android"
            }
        }
    }
    headers = {**COMMON_HEADERS, "Content-Type": "application/json"}
    url = "https://jiotvapi.media.jio.com/userservice/apis/v1/loginotp/verify"
    
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=12)
        data = resp.json()
        d = data.get("data", data)
        if d.get("authToken"):
            return {
                "success": True,
                "creds": {
                    "ssoToken": d.get("ssoToken"),
                    "authToken": d.get("authToken"),
                    "refreshToken": d.get("refreshToken"),
                    "deviceId": "3c6d6b5702fa09bd",
                    "subscriberId": d.get("sessionAttributes", {}).get("user", {}).get("subscriberId"),
                    "uniqueId": d.get("sessionAttributes", {}).get("user", {}).get("unique")
                }
            }
        else:
            return {"success": False, "message": data.get("message", "Verification failed"), "raw": data}
    except Exception as e:
        return {"success": False, "error": str(e)}

def refresh_auth_token(creds: dict) -> dict:
    """Refresh authToken using refreshToken."""
    refresh_tok = creds.get("refreshToken")
    if not refresh_tok:
        return {"success": False, "message": "No refreshToken present"}
        
    payload = {
        "appName": "RJIL_JioTV",
        "deviceId": creds.get("deviceId", "3c6d6b5702fa09bd"),
        "refreshToken": refresh_tok
    }
    headers = {
        "devicetype": "phone",
        "versionCode": "290",
        "os": "android",
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": "okhttp/4.2.2"
    }
    url = "https://auth.media.jio.com/tokenservice/apis/v1/refreshtoken?langId=6"
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        data = resp.json()
        new_auth = data.get("authToken")
        if new_auth:
            creds["authToken"] = new_auth
            if data.get("refreshToken"):
                creds["refreshToken"] = data["refreshToken"]
            return {"success": True, "authToken": new_auth}
        return {"success": False, "message": data.get("message", "Refresh failed")}
    except Exception as e:
        return {"success": False, "error": str(e)}

def self_mint_token(creds: dict, channel_id: str = "144") -> str:
    """
    Directly mint a live Akamai __hdnea__ wildcard token (acl=/*)
    using Jio's official playback API.
    """
    url = "https://jiotvapi.media.jio.com/playback/apis/v1/geturl?langId=6"
    headers = {
        "appkey": "NzNiMDhlYzQyNjJm",
        "devicetype": "phone",
        "os": "android",
        "deviceId": creds.get("deviceId", "3c6d6b5702fa09bd"),
        "isott": "false",
        "channel_id": channel_id,
        "accesstoken": creds.get("authToken", ""),
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "okhttp/4.2.2"
    }
    body = f"stream_type=Seek&channel_id={channel_id}"
    
    try:
        resp = requests.post(url, headers=headers, data=body, timeout=10)
        if resp.status_code == 419:
            # Token expired, try refreshing
            print("  🔄 Jio authToken expired (419), attempting auto-refresh...")
            ref = refresh_auth_token(creds)
            if ref.get("success"):
                headers["accesstoken"] = creds["authToken"]
                resp = requests.post(url, headers=headers, data=body, timeout=10)
            else:
                print(f"  ❌ Refresh failed: {ref.get('message')}")
                return ""

        if resp.status_code == 200:
            data = resp.json()
            result_url = data.get("result", "")
            m = re.search(r'(__hdnea__=st=\d+~exp=\d+~acl=/\*~hmac=[a-f0-9]+)', result_url)
            if m:
                return m.group(1)
            # Sometimes acl is specific to channel; match any valid __hdnea__
            m2 = re.search(r'(__hdnea__=st=\d+~exp=\d+~acl=[^~&]+~hmac=[a-f0-9]+)', result_url)
            if m2:
                return m2.group(1)
        else:
            print(f"  ⚠️ Jio geturl returned status {resp.status_code}: {resp.text[:150]}")
    except Exception as e:
        print(f"  ⚠️ Error during self_mint_token: {e}")
        
    return ""

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python jio_auth.py send <10-digit-mobile>")
        print("  python jio_auth.py verify <10-digit-mobile> <otp>")
        print("  python jio_auth.py mint <creds_json_file>")
        sys.exit(1)
        
    cmd = sys.argv[1].lower()
    if cmd == "send":
        mobile = sys.argv[2]
        res = send_otp(mobile)
        print("Send OTP result:", res)
    elif cmd == "verify":
        mobile = sys.argv[2]
        otp = sys.argv[3]
        res = verify_otp(mobile, otp)
        print("Verify OTP result:", res)
    elif cmd == "mint":
        creds_file = sys.argv[2]
        with open(creds_file, "r", encoding="utf-8") as f:
            c = json.load(f)
        tok = self_mint_token(c)
        print("Minted token:", tok)
