from __future__ import annotations

import time
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
    ),
    "Accept-Language": "es-419,es;q=0.9,en;q=0.7",
}


def build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        status=3,
        backoff_factor=0.6,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "HEAD"}),
        respect_retry_after_header=True,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10))
    session.mount("http://", HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10))
    session.headers.update(DEFAULT_HEADERS)
    return session


def get(
    session: requests.Session,
    url: str,
    *,
    timeout: int = 20,
    allow_redirects: bool = True,
    delay_seconds: float = 0.0,
    referer: Optional[str] = None,
) -> requests.Response:
    if delay_seconds > 0:
        time.sleep(delay_seconds)
    headers = {"Referer": referer} if referer else None
    response = session.get(url, timeout=timeout, allow_redirects=allow_redirects, headers=headers)
    response.raise_for_status()
    return response
