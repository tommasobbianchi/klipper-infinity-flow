#!/usr/bin/env python3
"""
Infinity Flow S1+ Network & BLE Reconnaissance
================================================
Scans the local network to discover S1+ devices and their exposed services.
Run from any machine on the same WiFi as the S1+.

Usage:
    python3 recon_s1plus.py                    # Auto-discover via mDNS + ARP
    python3 recon_s1plus.py --ip 192.168.0.XX  # Scan a known IP
    python3 recon_s1plus.py --ble              # BLE GATT scan (needs bleak)

Requirements:
    pip install scapy bleak aiohttp
    (scapy and bleak are optional - script degrades gracefully)
"""

import argparse
import asyncio
import json
import socket
import subprocess
import sys
import time
from typing import Optional, List, Dict


# ── Network Discovery ───────────────────────────────────────

def discover_via_arp(subnet: str = "192.168.0") -> List[Dict]:
    """Scan ARP table for ESP32 devices (Espressif OUI prefixes)."""
    # Espressif MAC OUI prefixes
    espressif_ouis = [
        "24:0a:c4", "24:6f:28", "30:ae:a4", "3c:61:05",
        "3c:71:bf", "40:f5:20", "54:32:04", "58:bf:25",
        "68:67:25", "70:04:1d", "7c:9e:bd", "7c:df:a1",
        "80:7d:3a", "84:0d:8e", "84:cc:a8", "84:f3:eb",
        "8c:4b:14", "94:3c:c6", "94:b5:55", "94:b9:7e",
        "a0:20:a6", "a4:cf:12", "a8:03:2a", "a8:42:e3",
        "ac:67:b2", "b4:e6:2d", "b8:d6:1a", "bc:dd:c2",
        "c0:49:ef", "c4:4f:33", "c4:dd:57", "c8:2b:96",
        "c8:f0:9e", "cc:50:e3", "cc:7b:5c", "d4:d4:da",
        "d8:a0:1d", "d8:bc:38", "dc:54:75", "e0:5a:1b",
        "e0:98:06", "e8:31:cd", "e8:68:e7", "e8:9f:6d",
        "ec:62:60", "ec:64:c9", "ec:94:cb", "f0:08:d1",
        "f4:12:fa", "f4:cf:a2", "fc:f5:c4",
        "34:85:18", "48:27:e2", "dc:da:0c",  # ESP32-S3 common
    ]
    
    print("[*] Scanning ARP table for Espressif (ESP32) devices...")
    
    # Ping sweep to populate ARP
    try:
        subprocess.run(
            ["bash", "-c", f"for i in $(seq 1 254); do ping -c1 -W1 {subnet}.$i &>/dev/null & done; wait"],
            timeout=30, capture_output=True)
    except Exception:
        pass
    
    # Read ARP table
    try:
        result = subprocess.run(["arp", "-a"], capture_output=True, text=True)
        lines = result.stdout.strip().split('\n')
    except Exception:
        result = subprocess.run(["ip", "neigh", "show"], capture_output=True, text=True)
        lines = result.stdout.strip().split('\n')
    
    found = []
    for line in lines:
        line_lower = line.lower()
        for oui in espressif_ouis:
            if oui.lower() in line_lower:
                # Extract IP
                parts = line.split()
                ip = None
                mac = None
                for p in parts:
                    if '.' in p and p[0].isdigit():
                        ip = p.strip('()')
                    if ':' in p and len(p) >= 17:
                        mac = p
                if ip:
                    found.append({"ip": ip, "mac": mac or "unknown", "oui_match": oui})
                break
    
    if found:
        print(f"[+] Found {len(found)} Espressif device(s):")
        for d in found:
            print(f"    {d['ip']}  MAC: {d['mac']}")
    else:
        print("[-] No Espressif devices found in ARP table")
        print("    Make sure S1+ is powered on and connected to WiFi")
    
    return found


def discover_via_mdns() -> List[Dict]:
    """Try mDNS discovery for ESP32 devices."""
    print("[*] Scanning mDNS for .local devices...")
    found = []
    
    try:
        result = subprocess.run(
            ["avahi-browse", "-a", "--resolve", "-t", "-p"],
            capture_output=True, text=True, timeout=10)
        for line in result.stdout.split('\n'):
            if 'esp32' in line.lower() or 'infinity' in line.lower() or 's1' in line.lower():
                found.append({"mdns_entry": line.strip()})
                print(f"    [+] mDNS: {line.strip()}")
    except FileNotFoundError:
        print("    avahi-browse not found, trying dns-sd...")
        try:
            result = subprocess.run(
                ["dns-sd", "-B", "_http._tcp", "local"],
                capture_output=True, text=True, timeout=5)
            print(f"    {result.stdout[:500]}")
        except Exception:
            print("    [-] No mDNS tools available")
    except subprocess.TimeoutExpired:
        print("    [-] mDNS scan timed out")
    
    return found


def port_scan(ip: str, ports: List[int] = None) -> List[int]:
    """Quick TCP port scan."""
    if ports is None:
        # Common IoT/ESP32 ports
        ports = [
            80, 443, 8080, 8443,        # HTTP/HTTPS
            81, 8081,                     # Alt HTTP (ESPAsyncWebServer common)
            1883, 8883,                   # MQTT
            5353,                         # mDNS
            3232,                         # Arduino OTA
            23, 2323,                     # Telnet
            4443, 4444,                   # Custom/debug
            9090, 9100,                   # Monitoring
            5555,                         # ADB
            6053, 6052,                   # ESPHome native API
            443, 8443, 8883,             # TLS variants
            53,                           # DNS
        ]
    
    print(f"[*] Port scanning {ip} ({len(ports)} ports)...")
    open_ports = []
    
    for port in ports:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        try:
            result = sock.connect_ex((ip, port))
            if result == 0:
                open_ports.append(port)
                # Try to grab banner
                banner = ""
                try:
                    sock.send(b"GET / HTTP/1.0\r\nHost: %s\r\n\r\n" % ip.encode())
                    banner = sock.recv(512).decode('utf-8', errors='replace')[:200]
                except Exception:
                    pass
                print(f"    [+] Port {port} OPEN  {banner[:100]}")
        except Exception:
            pass
        finally:
            sock.close()
    
    if not open_ports:
        print("    [-] No open TCP ports found")
    
    return open_ports


async def http_probe(ip: str, port: int) -> Optional[Dict]:
    """Probe an HTTP endpoint for API info."""
    import aiohttp
    
    paths = [
        "/", "/api", "/status", "/info", "/device",
        "/api/v1/status", "/api/device", "/api/info",
        "/rpc", "/json", "/data", "/sensor",
        "/filament", "/flowq",
        "/.well-known/", "/generate_204",
    ]
    
    results = {}
    print(f"\n[*] HTTP probing {ip}:{port}...")
    
    timeout = aiohttp.ClientTimeout(total=3)
    
    for scheme in ["http"]:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for path in paths:
                url = f"{scheme}://{ip}:{port}{path}"
                try:
                    async with session.get(url) as resp:
                        status = resp.status
                        content_type = resp.headers.get('Content-Type', '')
                        body = await resp.text()
                        headers = dict(resp.headers)
                        
                        if status != 404:
                            results[path] = {
                                "status": status,
                                "content_type": content_type,
                                "body_preview": body[:500],
                                "server": headers.get("Server", ""),
                            }
                            print(f"    [+] {url} -> {status} ({content_type})")
                            if body and len(body) < 500:
                                print(f"        Body: {body[:300]}")
                except Exception as e:
                    pass
    
    return results


# ── BLE Discovery ───────────────────────────────────────────

async def ble_scan(duration: int = 15) -> List[Dict]:
    """Scan for BLE devices, looking for S1+ GATT services."""
    try:
        from bleak import BleakScanner, BleakClient
    except ImportError:
        print("[-] bleak not installed. Install with: pip install bleak")
        return []
    
    print(f"[*] BLE scanning for {duration}s...")
    
    devices = await BleakScanner.discover(timeout=duration)
    
    s1_candidates = []
    for d in devices:
        name = d.name or ""
        # Look for S1+ by name pattern
        if any(kw in name.lower() for kw in ["s1", "infinity", "flow", "if-"]):
            s1_candidates.append(d)
            print(f"    [+] MATCH: {d.name} ({d.address}) RSSI={d.rssi}")
        elif "esp" in name.lower():
            print(f"    [?] ESP device: {d.name} ({d.address}) RSSI={d.rssi}")
    
    if not s1_candidates:
        print("    [-] No S1+ candidates found by name")
        print("    [*] Listing ALL nearby BLE devices:")
        for d in sorted(devices, key=lambda x: x.rssi or -100, reverse=True)[:20]:
            print(f"        {d.name or '(unnamed)':30s} {d.address}  RSSI={d.rssi}")
        print()
        print("    [!] The S1+ might be one of the unnamed devices.")
        print("    [!] Try pressing the BT button on the S1+ for 3s,")
        print("        then re-run with --ble to see it appear.")
    
    # Try connecting to candidates and reading GATT
    for candidate in s1_candidates:
        print(f"\n[*] Connecting to {candidate.name} ({candidate.address})...")
        try:
            async with BleakClient(candidate.address, timeout=10) as client:
                print(f"    [+] Connected!")
                print(f"    [*] Enumerating GATT services...")
                
                for service in client.services:
                    print(f"\n    Service: {service.uuid}")
                    print(f"      Description: {service.description}")
                    
                    for char in service.characteristics:
                        props = ", ".join(char.properties)
                        print(f"      Char: {char.uuid}  [{props}]")
                        print(f"        Description: {char.description}")
                        
                        # Try reading if readable
                        if "read" in char.properties:
                            try:
                                value = await client.read_gatt_char(char.uuid)
                                # Try decode as UTF-8, fall back to hex
                                try:
                                    text = value.decode('utf-8')
                                    print(f"        Value (str): {text}")
                                except UnicodeDecodeError:
                                    print(f"        Value (hex): {value.hex()}")
                                    print(f"        Value (raw): {list(value)}")
                            except Exception as e:
                                print(f"        Read error: {e}")
                        
                        # List descriptors
                        for desc in char.descriptors:
                            print(f"        Desc: {desc.uuid} = {desc.description}")
                            try:
                                val = await client.read_gatt_descriptor(desc.handle)
                                print(f"          Value: {val}")
                            except Exception:
                                pass
                
        except Exception as e:
            print(f"    [-] Connection failed: {e}")
    
    return [{"name": d.name, "address": d.address, "rssi": d.rssi} 
            for d in s1_candidates]


# ── Main ────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(
        description="Infinity Flow S1+ Network & BLE Reconnaissance")
    parser.add_argument("--ip", help="Known S1+ IP address to scan")
    parser.add_argument("--subnet", default="192.168.0",
                        help="Subnet to scan (default: 192.168.0)")
    parser.add_argument("--ble", action="store_true",
                        help="Enable BLE GATT scanning")
    parser.add_argument("--all", action="store_true",
                        help="Run all scans")
    args = parser.parse_args()

    print("=" * 60)
    print("  Infinity Flow S1+ Reconnaissance Tool")
    print("  Native Ricerca - klipper-infinity-flow")
    print("=" * 60)
    print()

    target_ips = []

    # Step 1: Network discovery
    if args.ip:
        target_ips = [args.ip]
        print(f"[*] Using provided IP: {args.ip}")
    else:
        # mDNS
        mdns_results = discover_via_mdns()
        print()
        
        # ARP scan
        arp_results = discover_via_arp(args.subnet)
        target_ips = [d["ip"] for d in arp_results]
        print()

    # Step 2: Port scan discovered devices
    for ip in target_ips:
        open_ports = port_scan(ip)
        
        # Step 3: HTTP probe open ports
        http_ports = [p for p in open_ports if p in [80, 443, 8080, 8443, 81, 8081, 4443]]
        for port in http_ports:
            try:
                results = await http_probe(ip, port)
            except ImportError:
                print("    [-] aiohttp not installed, skipping HTTP probe")
                print("        pip install aiohttp")
                break
        
        print()

    # Step 4: BLE scan
    if args.ble or args.all:
        print()
        ble_results = await ble_scan()
        print()

    # Summary
    print("=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    print()
    if target_ips:
        print(f"  Espressif devices found: {len(target_ips)}")
        for ip in target_ips:
            print(f"    - {ip}")
    else:
        print("  No Espressif devices auto-discovered.")
        print("  Try: python3 recon_s1plus.py --ip <S1+ IP>")
        print("  (Check your router's DHCP leases for the S1+ IP)")
    print()
    print("  Next steps:")
    print("    1. If HTTP ports found: we can build a direct Moonraker component")
    print("    2. If BLE characteristics readable: Moonraker can poll via BLE")  
    print("    3. If nothing exposed: hardware GPIO tap is the fallback")
    print()


if __name__ == "__main__":
    asyncio.run(main())
