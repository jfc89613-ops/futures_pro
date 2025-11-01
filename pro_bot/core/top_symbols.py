import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Sequence, Set

from .client import get_client

log = logging.getLogger("symbols")

_CACHE_DIR = Path("cache")
_CACHE_FILE = _CACHE_DIR / "top_usdtm_quote_volume.json"
_CACHE_TTL = timedelta(hours=24)
_DEFAULT_FETCH_SIZE = 50


def usdt_perpetual_set() -> Set[str]:
    info = get_client().exchange_info()
    perps: Set[str] = set()
    for s in info["symbols"]:
        if (
            s.get("contractType") == "PERPETUAL"
            and s.get("quoteAsset") == "USDT"
            and s.get("status") == "TRADING"
        ):
            perps.add(s["symbol"])
    return perps


def _load_cached_symbols(min_len: int) -> Optional[Sequence[str]]:
    try:
        raw = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as exc:
        log.warning("[CTX] cache corrupt (%s), refetching", exc)
        return None

    fetched_raw = raw.get("fetched_at")
    symbols = raw.get("symbols") or []
    if not isinstance(symbols, list):
        return None
    if fetched_raw is None:
        return None

    try:
        fetched_at = datetime.fromisoformat(fetched_raw)
    except ValueError:
        return None
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)

    now_utc = datetime.now(timezone.utc)
    if now_utc - fetched_at > _CACHE_TTL:
        return None
    if len(symbols) < min_len:
        return None
    return list(symbols)


def _persist_symbols(symbols: Sequence[str]) -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "symbols": list(symbols),
    }
    _CACHE_FILE.write_text(json.dumps(payload), encoding="utf-8")


def _fetch_symbols(
    limit: int,
    allow: Set[str],
    *,
    stats: Optional[Sequence[dict]] = None,
) -> List[str]:
    if stats is None:
        stats = get_client().futures_ticker()  # 24hr stats list
    rows = []
    for it in stats:
        sym = it.get("symbol")
        if sym not in allow:
            continue
        try:
            qv = float(it.get("quoteVolume", 0.0))
        except Exception:
            qv = 0.0
        rows.append((qv, sym))
    rows.sort(reverse=True)
    return [s for _, s in rows[:limit]]


def top_usdtm_by_quote_volume(
    n: int = 20,
    allow: Optional[Set[str]] = None,
    *,
    force_refresh: bool = False,
) -> List[str]:
    target = max(n, 1)
    cached: Optional[Sequence[str]] = None
    if not force_refresh:
        cached = _load_cached_symbols(target)
        if cached:
            filtered = [s for s in cached if allow is None or s in allow]
            if len(filtered) >= target:
                log.info("[CTX] usando cache de top symbols (%d)", len(filtered))
                return filtered[:target]

    log.info("[CTX] refrescando top symbols top=%d", target)
    fetch_size = max(target, _DEFAULT_FETCH_SIZE)
    stats = get_client().futures_ticker()
    full_allow = usdt_perpetual_set()
    allow_set = allow or full_allow
    symbols = _fetch_symbols(fetch_size, allow_set, stats=stats)
    if allow is None:
        base_symbols = symbols
    else:
        base_symbols = _fetch_symbols(fetch_size, full_allow, stats=stats)
    _persist_symbols(base_symbols)

    return symbols[:target]
