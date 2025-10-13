# src/utils/net.py
from __future__ import annotations
import ssl
import socket
import certifi
import aiohttp

def default_ssl_context() -> ssl.SSLContext:
    # Use certifi’s CA bundle to avoid local/corp chain issues
    ctx = ssl.create_default_context(cafile=certifi.where())
    return ctx

def default_connector() -> aiohttp.TCPConnector:
    return aiohttp.TCPConnector(
        ssl=default_ssl_context(),
        family=socket.AF_INET,          # Prefer IPv4 (avoids flaky IPv6 on some networks)
        limit=8,
        limit_per_host=4,
        enable_cleanup_closed=True,
        force_close=False,
        keepalive_timeout=15,
    )

def default_headers() -> dict:
    # Friendly UA — some endpoints are picky (Crossref/arXiv)
    return {
        "User-Agent": "ModelCardGen/1.0 (+https://example.invalid) Python/aiohttp",
        "Accept": "application/json, text/xml, */*;q=0.8",
    }

def default_timeout() -> aiohttp.ClientTimeout:
    return aiohttp.ClientTimeout(total=25, connect=10, sock_read=15)

def new_session() -> aiohttp.ClientSession:
    # trust_env=True lets aiohttp use HTTPS_PROXY/HTTP_PROXY/NO_PROXY if they’re set
    return aiohttp.ClientSession(
        timeout=default_timeout(),
        connector=default_connector(),
        trust_env=True,
        headers=default_headers(),
    )
