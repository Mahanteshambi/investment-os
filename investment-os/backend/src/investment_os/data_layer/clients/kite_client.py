"""Typed KiteConnect client for the Investment OS data layer.

Token lifecycle
───────────────
Kite access tokens expire at midnight IST every day.  There is no OAuth
refresh token — the user must complete the web login flow once per day.

Strategy implemented here:
  1. On first call, load token from env (KITE_ACCESS_TOKEN) or from the
     token cache file (data/kite_token.json) — whichever was updated today.
  2. After a successful exchange_token(), write the new token to both the
     .env file and the token cache file.
  3. On any 403 / TokenException, raise KiteAuthError with the login URL
     embedded in the message.  The caller (scheduler / API route) is
     responsible for surfacing this to the user.

Import path:
    from investment_os.data_layer.clients.kite_client import KiteClient
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any

from investment_os.core.config import settings
from investment_os.core.logging import get_logger
from investment_os.data_layer.models.price import OHLCBar  # canonical — no local copy

logger = get_logger(__name__)


# ── Exceptions ────────────────────────────────────────────────────────────────

class KiteAuthError(Exception):
    """Raised when the Kite access token is missing, expired, or invalid."""


class KiteAPIError(Exception):
    """Raised for non-auth Kite API failures."""


# ── Domain types returned by this client ─────────────────────────────────────

class RawHolding:
    """Minimal holding record returned by Kite before classification."""

    __slots__ = (
        "ticker", "instrument_type", "quantity",
        "avg_cost", "last_price", "isin",
    )

    def __init__(
        self,
        ticker: str,
        instrument_type: str,
        quantity: float,
        avg_cost: float,
        last_price: float,
        isin: str = "",
    ) -> None:
        self.ticker = ticker
        self.instrument_type = instrument_type
        self.quantity = quantity
        self.avg_cost = avg_cost
        self.last_price = last_price
        self.isin = isin


# ── Token cache helpers ───────────────────────────────────────────────────────

def _load_cached_token() -> str:
    """Return today's access token from the JSON cache, or '' if stale/missing."""
    cache_path: Path = settings.kite_token_cache_path
    if not cache_path.exists():
        return ""
    try:
        data = json.loads(cache_path.read_text())
        generated = date.fromisoformat(data.get("generated_at", "")[:10])
        if generated == date.today():
            return data.get("access_token", "")
    except Exception as exc:
        logger.debug("Token cache unreadable: %s", exc)
    return ""


def _save_cached_token(access_token: str) -> None:
    """Persist access token to the JSON cache file."""
    cache_path: Path = settings.kite_token_cache_path
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "access_token": access_token,
        "generated_at": datetime.now().isoformat(),
    }
    cache_path.write_text(json.dumps(payload, indent=2))
    logger.debug("Kite token cached at %s", cache_path)



# ── Client ────────────────────────────────────────────────────────────────────

class KiteClient:
    """Typed wrapper around kiteconnect.KiteConnect.

    Thread-safe for read operations (holdings, historical data).
    Token exchange must happen in a single-threaded context (startup / login).
    """

    def __init__(self) -> None:
        self._api_key: str = settings.kite_api_key
        self._api_secret: str = settings.kite_api_secret
        self._access_token: str = ""
        self._kite: Any = None  # kiteconnect.KiteConnect, typed as Any to keep dep optional

    # ── Auth helpers ──────────────────────────────────────────────────────────

    def _resolve_token(self) -> str:
        """Return the best available access token (env > cache)."""
        # env var takes precedence (set by the process at runtime)
        env_token = os.environ.get("KITE_ACCESS_TOKEN", "").strip() or settings.kite_access_token
        if env_token:
            return env_token
        return _load_cached_token()

    def _ensure_kite(self) -> Any:
        """Return an authenticated KiteConnect instance, raising KiteAuthError if not possible."""
        token = self._resolve_token()
        if not token:
            raise KiteAuthError(
                "No valid Kite access token found.  "
                f"Visit {self.get_login_url()} to authenticate."
            )

        # Re-create the kite object if the token changed (e.g. after daily refresh)
        if self._kite is None or token != self._access_token:
            try:
                from kiteconnect import KiteConnect  # type: ignore[import-untyped]
            except ImportError as exc:
                raise RuntimeError("kiteconnect package not installed") from exc

            if not self._api_key:
                raise KiteAuthError("KITE_API_KEY is not set.")

            kite = KiteConnect(api_key=self._api_key)
            kite.set_access_token(token)
            self._kite = kite
            self._access_token = token
            logger.debug("KiteConnect initialised with token …%s", token[-6:])

        return self._kite

    def _call(self, fn_name: str, *args: Any, **kwargs: Any) -> Any:
        """Call a KiteConnect method, converting auth errors to KiteAuthError."""
        try:
            from kiteconnect.exceptions import (  # type: ignore[import-untyped]
                TokenException, PermissionException,
            )
        except ImportError:
            TokenException = PermissionException = Exception  # fallback

        kite = self._ensure_kite()
        try:
            return getattr(kite, fn_name)(*args, **kwargs)
        except (TokenException, PermissionException) as exc:
            raise KiteAuthError(
                f"Kite auth failed ({fn_name}): {exc}.  "
                f"Re-authenticate at {self.get_login_url()}"
            ) from exc
        except Exception as exc:
            raise KiteAPIError(f"Kite API error ({fn_name}): {exc}") from exc

    # ── Public API ────────────────────────────────────────────────────────────

    def get_login_url(self) -> str:
        """Return the Kite web login URL for the configured API key."""
        if not self._api_key:
            raise KiteAuthError("KITE_API_KEY is not set.  Cannot generate login URL.")
        try:
            from kiteconnect import KiteConnect  # type: ignore[import-untyped]
        except ImportError as exc:
            raise RuntimeError("kiteconnect package not installed") from exc
        return KiteConnect(api_key=self._api_key).login_url()

    def exchange_token(self, request_token: str) -> str:
        """Exchange a one-time request_token for an access token.

        Persists the new token to the .env file and the JSON cache.
        Returns the access_token string.
        """
        if not self._api_key or not self._api_secret:
            raise KiteAuthError("KITE_API_KEY and KITE_API_SECRET must be set for token exchange.")

        try:
            from kiteconnect import KiteConnect  # type: ignore[import-untyped]
        except ImportError as exc:
            raise RuntimeError("kiteconnect package not installed") from exc

        kite = KiteConnect(api_key=self._api_key)
        try:
            session = kite.generate_session(request_token, api_secret=self._api_secret)
        except Exception as exc:
            raise KiteAuthError(f"Token exchange failed: {exc}") from exc

        access_token = session.get("access_token", "")
        if not access_token:
            raise KiteAuthError("Kite did not return an access_token in the session response.")

        # Update runtime state
        self._access_token = str(access_token)
        self._kite = kite
        self._kite.set_access_token(self._access_token)
        os.environ["KITE_ACCESS_TOKEN"] = self._access_token

        # Persist to JSON cache only (survives process restarts within the same day)
        _save_cached_token(self._access_token)

        login_time = session.get("login_time")
        logger.info("Kite token exchanged successfully. Login time: %s", login_time)

        # Print clearly so the token can be manually copied to .env
        print("\n" + "=" * 60)
        print("KITE ACCESS TOKEN — copy this to your .env file:")
        print(f"  KITE_ACCESS_TOKEN={self._access_token}")
        print("=" * 60 + "\n")

        return self._access_token

    def is_connected(self) -> bool:
        """Return True if the current token can reach the Kite API."""
        try:
            self._call("profile")
            return True
        except (KiteAuthError, KiteAPIError):
            return False

    def get_holdings(self) -> list[RawHolding]:
        """Fetch equity + MF holdings from Kite.

        Returns a list of RawHolding objects.  Classification (ETF vs equity
        vs gold, etc.) is left to the repository / service layer.
        """
        raw: list[dict] = self._call("holdings")

        # Attempt MF holdings — non-fatal if it fails
        try:
            mf_raw: list[dict] = self._call("mf_holdings")
            for mf in mf_raw:
                mf.setdefault("instrument_type", "MUTUAL FUND")
                if "tradingsymbol" not in mf and "fund" in mf:
                    mf["tradingsymbol"] = mf["fund"]
            raw.extend(mf_raw)
        except KiteAPIError as exc:
            logger.warning("MF holdings unavailable: %s", exc)

        results: list[RawHolding] = []
        for h in raw:
            qty = float(h.get("quantity", 0))
            if qty == 0:
                continue  # skip zero-quantity positions
            results.append(
                RawHolding(
                    ticker=h.get("tradingsymbol", ""),
                    instrument_type=h.get("instrument_type", "EQ"),
                    quantity=qty,
                    avg_cost=float(h.get("average_price", 0)),
                    last_price=float(h.get("last_price", 0)),
                    isin=h.get("isin", ""),
                )
            )
        logger.info("Fetched %d holdings from Kite", len(results))
        return results

    def get_mf_instrument_names(self) -> dict[str, str]:
        """Return a mapping of MF tradingsymbol → fund name."""
        try:
            instruments: list[dict] = self._call("mf_instruments")
            return {
                inst["tradingsymbol"]: inst["name"]
                for inst in instruments
                if "tradingsymbol" in inst and "name" in inst
            }
        except KiteAPIError as exc:
            logger.warning("Could not fetch MF instruments: %s", exc)
            return {}

    def get_historical_data(
        self,
        instrument_token: int,
        from_date: str,
        to_date: str,
        interval: str = "day",
    ) -> list[OHLCBar]:
        """Fetch OHLCV candles for an instrument.

        Args:
            instrument_token: Kite numeric instrument token.
            from_date: "YYYY-MM-DD" or "YYYY-MM-DD HH:MM:SS".
            to_date:   "YYYY-MM-DD" or "YYYY-MM-DD HH:MM:SS".
            interval:  "minute", "3minute", "5minute", "10minute",
                       "15minute", "30minute", "60minute", "day".

        Returns:
            List of OHLCBar, oldest first.
        """
        candles: list[dict] = self._call(
            "historical_data", instrument_token, from_date, to_date, interval
        )
        bars = [OHLCBar.from_kite_candle(c) for c in candles]
        logger.debug(
            "Fetched %d bars for token %d (%s → %s)",
            len(bars), instrument_token, from_date, to_date,
        )
        return bars

    def get_margins(self) -> dict[str, Any]:
        """Return available cash and margin details."""
        return self._call("margins")  # type: ignore[return-value]

    def get_gtts(self) -> list[dict[str, Any]]:
        """Return all active GTT orders."""
        return self._call("get_gtts")  # type: ignore[return-value]

    def get_positions(self) -> list[dict[str, Any]]:
        """Return net intraday positions."""
        pos = self._call("positions")
        return pos.get("net", [])

    def get_completed_orders(self) -> list[dict[str, Any]]:
        """Return today's COMPLETE orders."""
        orders: list[dict] = self._call("orders")
        return [o for o in orders if o.get("status") == "COMPLETE"]
