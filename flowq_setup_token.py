#!/usr/bin/env python3
"""
FlowQ Token Setup Script
=========================
Fetches a FlowQ refresh_token using your account credentials.
Run this once to get the token, then paste it in moonraker.conf.

Usage:
    python3 flowq_setup_token.py

Requirements:
    pip install aiohttp
"""

import asyncio
import json
import os
import sys
import getpass

FLOWQ_API = "https://api.infinityflow3d.com/api"
HEADERS = {
    "Content-Type": "application/json",
    "Origin": "https://flowq.infinityflow3d.com",
    "Referer": "https://flowq.infinityflow3d.com/",
    "User-Agent": "klipper-infinity-flow/2.0",
}


async def login(email: str, password: str) -> dict:
    try:
        import aiohttp
    except ImportError:
        print("ERROR: aiohttp not installed. Run: pip install aiohttp")
        sys.exit(1)

    print(f"\n[*] Logging in as {email}...")
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{FLOWQ_API}/v1/identity/login",
            json={"email": email, "password": password},
            headers=HEADERS,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            body = await resp.text()
            if resp.status != 200:
                print(f"[-] Login failed (HTTP {resp.status}): {body}")
                if "No password" in body or resp.status == 400:
                    print()
                    print("NOTE: Your account uses Google OAuth (no password set).")
                    print("To use email/password login, set a password at:")
                    print("  https://flowq.infinityflow3d.com/settings")
                    print()
                    print("Alternatively, extract your token from the browser:")
                    print("  1. Open https://flowq.infinityflow3d.com in Chrome/Firefox")
                    print("  2. Press F12 > Application tab > Local Storage")
                    print("     > https://flowq.infinityflow3d.com")
                    print("  3. Find 'refresh_token' and copy its value")
                    print("  4. Paste it in moonraker.conf as refresh_token:")
                sys.exit(1)
            try:
                return await resp.json()
            except Exception:
                print(f"[-] Unexpected response: {body}")
                sys.exit(1)


async def get_devices(access_token: str) -> list:
    try:
        import aiohttp
    except ImportError:
        sys.exit(1)

    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{FLOWQ_API}/v1/s1plus/devices",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status == 200:
                return await resp.json()
            return []


async def main():
    print("=" * 60)
    print("  FlowQ Token Setup for Klipper Infinity Flow")
    print("=" * 60)
    print()

    email = input("FlowQ email: ").strip()
    password = getpass.getpass("FlowQ password: ")

    data = await login(email, password)

    access_token = data.get("access_token")
    refresh_token = data.get("refresh_token")

    if not access_token:
        print(f"[-] No access_token in response: {data}")
        sys.exit(1)

    print(f"[+] Login successful!")
    # Never print full tokens to stdout — they're secrets
    print(f"    access_token:  {access_token[:12]}… (truncated)")
    if refresh_token:
        print(f"    refresh_token: {refresh_token[:12]}… (truncated, full value saved below)")

    # Fetch S1+ devices
    devices = await get_devices(access_token)
    if devices:
        print(f"\n[+] Found {len(devices)} S1+ device(s):")
        for d in devices:
            print(f"    - {d.get('name', 'unnamed')} "
                  f"(id={d['id']}, "
                  f"online={d.get('online', '?')}, "
                  f"state_a={d.get('state_a', '?')}, "
                  f"state_b={d.get('state_b', '?')})")
    else:
        print("\n[!] No S1+ devices found or couldn't fetch devices")

    # Print moonraker.conf snippet — full token shown here intentionally
    # (this is the ONE place the user needs to copy it)
    token_file = os.path.join(os.path.expanduser("~"), "flowq_tokens.json")
    print()
    print("=" * 60)
    print("Add this to your moonraker.conf:")
    print("=" * 60)
    print()
    print("[infinity_flow]")
    if refresh_token:
        print(f"refresh_token: {refresh_token}")
    else:
        print("# WARNING: No refresh_token received.")
        print("# This account may use Google OAuth — set a password at")
        print("# https://flowq.infinityflow3d.com/settings, then re-run.")
    if devices:
        print(f"# s1plus_id auto-detected: {devices[0]['id']}")
        print("# Uncomment the line below only if you have multiple S1+ devices:")
        print(f"# s1plus_id: {devices[0]['id']}")
    print()
    print("=" * 60)
    print(f"Full tokens also saved to: {token_file}")

    # Save tokens to a private file (chmod 600)
    out = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "devices": devices,
    }
    token_file = os.path.join(os.path.expanduser("~"), "flowq_tokens.json")
    import stat
    fd = os.open(token_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\n[+] Tokens saved to {token_file} (mode 600 — private)")


if __name__ == "__main__":
    asyncio.run(main())
