import logging
import time
from typing import Any, Callable

from binance.client import Client

from ..config import settings
from .rate_limit import RateLimiter

log = logging.getLogger("client")
FUTURES_MAIN_URL = "https://fapi.binance.com/fapi"
FUTURES_TESTNET_URL = "https://testnet.binancefuture.com/fapi"


class FuturesClient:
    def __init__(self):
        self.client = Client(settings.api_key, settings.api_secret, testnet=settings.testnet)
        # Forzar URL de Futuros correcta
        self.client.FUTURES_URL = FUTURES_TESTNET_URL if settings.testnet else FUTURES_MAIN_URL

        self._rest_limiter = RateLimiter(max(settings.rest_min_interval_ms / 1000.0, 0.05))

        # Sincronía de tiempo
        self.sync_time()

        # Aumentar pool HTTP para muchas peticiones concurrentes (evitar "Connection pool is full")
        try:
            self.client.REQUESTS_PARAMS = {"timeout": 10, "pool_maxsize": 200}
            sess = self.client.session
            from requests.adapters import HTTPAdapter

            adapter = HTTPAdapter(pool_connections=200, pool_maxsize=200)
            sess.mount("https://", adapter)
            sess.mount("http://", adapter)
        except Exception as exc:
            log.info(f"pool tuning: {exc}")

        # Configuración de cuenta (margin/leverage/position mode) para el símbolo principal
        self._configure_account()

    def _rest_call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Serialize REST calls to honour Binance limits."""
        self._rest_limiter.wait()
        return func(*args, **kwargs)

    def sync_time(self, retries: int = 3):
        for attempt in range(1, retries + 1):
            try:
                server_time = self.client.get_server_time()["serverTime"]
                local = int(time.time() * 1000)
                self.client._timestamp_offset = server_time - local
                log.info(f"Time sync OK. Offset: {self.client._timestamp_offset} ms")
                return
            except Exception as exc:
                log.warning(f"Time sync failed (attempt {attempt}): {exc}")
                time.sleep(attempt)
        raise RuntimeError("No se pudo sincronizar hora con Binance.")

    def _configure_account(self):
        symbol = settings.symbol
        try:
            self._rest_call(
                self.client.futures_change_margin_type,
                symbol=symbol,
                marginType=settings.margin_type,
            )
        except Exception as exc:
            log.info(f"margin_type: {exc}")
        try:
            self._rest_call(
                self.client.futures_change_leverage,
                symbol=symbol,
                leverage=settings.leverage,
            )
        except Exception as exc:
            log.info(f"leverage: {exc}")
        try:
            dual = "true" if settings.position_mode.upper() == "HEDGE" else "false"
            self._rest_call(self.client.futures_change_position_mode, dualSidePosition=dual)
        except Exception as exc:
            log.info(f"position_mode: {exc}")

    def exchange_info(self):
        return self._rest_call(self.client.futures_exchange_info)

    def account(self):
        return self._rest_call(self.client.futures_account)

    def ticker_price(self, symbol: str):
        return self._rest_call(self.client.futures_symbol_ticker, symbol=symbol)

    def futures_ticker(self, **kwargs: Any):
        return self._rest_call(self.client.futures_ticker, **kwargs)

    def futures_ticker_24hr(self, **kwargs: Any):
        func = getattr(self.client, "futures_ticker_24hr", None)
        if func is None:
            raise AttributeError("futures_ticker_24hr not available")
        return self._rest_call(func, **kwargs)

    def futures_klines(self, **kwargs: Any):
        return self._rest_call(self.client.futures_klines, **kwargs)

    def futures_position_information(self, **kwargs: Any):
        return self._rest_call(self.client.futures_position_information, **kwargs)

    def futures_get_open_orders(self, **kwargs: Any):
        return self._rest_call(self.client.futures_get_open_orders, **kwargs)

    def futures_create_order(self, **kwargs: Any):
        return self._rest_call(self.client.futures_create_order, **kwargs)

    def request_futures_api(self, method: str, path: str, **kwargs: Any):
        return self._rest_call(self.client._request_futures_api, method, path, **kwargs)

    def futures_stream_get_listen_key(self):
        return self._rest_call(self.client.futures_stream_get_listen_key)


client_singleton = None


def get_client():
    global client_singleton
    if client_singleton is None:
        client_singleton = FuturesClient()
    return client_singleton
