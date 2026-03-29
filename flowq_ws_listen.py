#!/usr/bin/env python3
"""
FlowQ WebSocket Live Listener
==============================
Connects to the FlowQ real-time WebSocket and prints all events.
This reveals what S1+ sensor data is available via the cloud API.

Usage:
    python3 flowq_ws_listen.py --email your@email.com --password yourpass

Or with API key (from flowq.infinityflow3d.com/settings):
    python3 flowq_ws_listen.py --apikey "key_id.secret"

Requirements:
    pip install websockets aiohttp
"""

import asyncio
import json
import sys
import argparse
import time
from datetime import datetime

BASE_API = "https://api.infinityflow3d.com/api"
WS_URL = "wss://ws.infinityflow3d.com/ws"  # /ws path, auth via ?token= query param


async def get_token_via_login(email: str, password: str) -> str:
    """Login with email/password and return access token."""
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{BASE_API}/v1/identity/login",
            json={"email": email, "password": password},
            headers={
                "Content-Type": "application/json",
                "Origin": "https://flowq.infinityflow3d.com",
            },
        ) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise RuntimeError(f"Login failed {resp.status}: {body}")
            data = await resp.json()
            print(f"[+] Login OK")
            return data.get("access_token") or data.get("token") or data.get("accessToken")


async def get_token_via_refresh(refresh_token: str) -> str:
    """Exchange refresh_token for access token, then get WS token."""
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{BASE_API}/v1/identity/token/refresh",
            json={"refresh_token": refresh_token},
            headers={
                "Content-Type": "application/json",
                "Origin": "https://flowq.infinityflow3d.com",
            },
        ) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise RuntimeError(f"Token refresh failed {resp.status}: {body}")
            data = await resp.json()
            return data["access_token"]


async def get_ws_token(access_token: str) -> str:
    """Exchange access token for WebSocket token."""
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{BASE_API}/v1/identity/ws/token",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Origin": "https://flowq.infinityflow3d.com",
            },
        ) as resp:
            if resp.status != 200:
                body = await resp.text()
                print(f"[!] WS token endpoint failed ({resp.status}): {body}")
                return access_token
            data = await resp.json()
            return data.get("token") or data.get("ws_token") or access_token


async def listen(token: str):
    """Connect to FlowQ WebSocket and print all events."""
    try:
        import websockets
    except ImportError:
        print("[-] websockets not installed. Run: pip install websockets")
        sys.exit(1)

    from urllib.parse import quote
    ws_url = f"{WS_URL}?token={quote(token)}"

    print(f"\n[*] Connecting to {WS_URL}?token=... ")
    print("[*] Waiting for events. Ctrl+C to stop.\n")
    print("=" * 70)

    async def heartbeat(ws):
        while True:
            await asyncio.sleep(25)
            await ws.send(json.dumps({"type": "ping"}))
            print(f"  [{datetime.now().strftime('%H:%M:%S')}] → ping")

    async for ws in websockets.connect(
        ws_url,
        ping_interval=None,  # Manual heartbeat
        max_size=2**20,
    ):
        try:
            hb_task = asyncio.create_task(heartbeat(ws))
            async for raw in ws:
                ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                try:
                    msg = json.loads(raw)
                    resource = msg.get("resource", "?")
                    patch = msg.get("patch", {})
                    updated_at = msg.get("updated_at", "")

                    # Highlight S1+ related events
                    is_s1 = any(
                        k in str(patch).lower()
                        for k in ["s1", "filament", "runout", "slot", "side", "sensor",
                                  "present", "empty", "feed", "motor"]
                    )
                    prefix = "🔴 S1+" if is_s1 else "   "

                    print(f"[{ts}] {prefix} resource={resource}")
                    print(f"         patch={json.dumps(patch, indent=2)}")
                    if updated_at:
                        print(f"         updated_at={updated_at}")
                    print()

                except json.JSONDecodeError:
                    print(f"[{ts}] RAW: {repr(raw[:300])}")

        except websockets.ConnectionClosed as e:
            hb_task.cancel()
            print(f"\n[!] Connection closed: {e}. Reconnecting in 3s...")
            await asyncio.sleep(3)


async def main():
    parser = argparse.ArgumentParser(description="FlowQ WebSocket listener")
    parser.add_argument("--email", help="FlowQ account email")
    parser.add_argument("--password", help="FlowQ account password")
    parser.add_argument("--refresh-token", help="FlowQ refresh_token JWT")
    parser.add_argument("--token", help="Direct WS token (skip login)")
    args = parser.parse_args()

    if args.token:
        token = args.token
    elif args.refresh_token:
        print("[*] Exchanging refresh token...")
        access = await get_token_via_refresh(args.refresh_token)
        print(f"[+] Access token: {access[:20]}...")
        token = await get_ws_token(access)
        print(f"[+] WS token: {token[:20]}...")
    elif args.email and args.password:
        access = await get_token_via_login(args.email, args.password)
        print(f"[+] Access token: {access[:20]}...")
        token = await get_ws_token(access)
        print(f"[+] WS token: {token[:20]}...")
    else:
        parser.print_help()
        print("\nExamples:")
        print("  python3 flowq_ws_listen.py --refresh-token eyJhbG...")
        print("  python3 flowq_ws_listen.py --email you@example.com --password pass")
        sys.exit(1)

    await listen(token)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[*] Stopped.")
