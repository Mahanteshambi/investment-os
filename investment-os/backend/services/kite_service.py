import logging
import os
import uuid
from pathlib import Path
from datetime import datetime

from models.schemas import HoldingCreate

logger = logging.getLogger(__name__)


class KiteService:
    def __init__(self):
        self.api_key = ""
        self.api_secret = ""
        self.access_token = ""
        self._kite = None
        self._refresh_credentials()

    def _refresh_credentials(self) -> None:
        new_token = os.getenv("KITE_ACCESS_TOKEN", "").strip()
        if new_token != self.access_token:
            self._kite = None  # force re-init with updated token
        self.api_key = os.getenv("KITE_API_KEY", "").strip()
        self.api_secret = os.getenv("KITE_API_SECRET", "").strip()
        self.access_token = new_token

    def _get_kite(self):
        self._refresh_credentials()
        if not self.api_key or not self.access_token:
            raise RuntimeError("Kite credentials missing. Set KITE_API_KEY and KITE_ACCESS_TOKEN.")
        if self._kite is None:
            try:
                from kiteconnect import KiteConnect
                self._kite = KiteConnect(api_key=self.api_key)
                self._kite.set_access_token(self.access_token)
            except Exception as e:
                raise RuntimeError(f"Kite init failed: {e}") from e
        return self._kite

    def get_login_url(self) -> str:
        self._refresh_credentials()
        if not self.api_key:
            raise RuntimeError("Kite API key missing. Set KITE_API_KEY.")
        try:
            from kiteconnect import KiteConnect
            kite = KiteConnect(api_key=self.api_key)
            return kite.login_url()
        except Exception as e:
            raise RuntimeError(f"Failed to generate Kite login URL: {e}") from e

    def create_access_session(self, request_token: str, persist: bool = True) -> datetime | None:
        self._refresh_credentials()
        if not self.api_key or not self.api_secret:
            raise RuntimeError("Kite API credentials missing. Set KITE_API_KEY and KITE_API_SECRET.")
        try:
            from kiteconnect import KiteConnect
            kite = KiteConnect(api_key=self.api_key)
            session = kite.generate_session(request_token, api_secret=self.api_secret)
            access_token = session.get("access_token")
            if not access_token:
                raise RuntimeError("Kite session did not return access token.")
            self.access_token = str(access_token)
            os.environ["KITE_ACCESS_TOKEN"] = self.access_token
            self._kite = kite
            self._kite.set_access_token(self.access_token)
            if persist:
                _upsert_env_var("KITE_ACCESS_TOKEN", self.access_token)
            return _parse_session_expiry(session.get("login_time"))
        except Exception as e:
            raise RuntimeError(f"Kite session generation failed: {e}") from e

    def is_connected(self) -> bool:
        kite = self._get_kite()
        if kite is None:
            return False
        try:
            kite.profile()
            return True
        except Exception:
            return False

    def get_holdings(self) -> list[HoldingCreate]:
        kite = self._get_kite()
        try:
            raw = kite.holdings()
            try:
                mf_raw = kite.mf_holdings()
                for mf in mf_raw:
                    mf["instrument_type"] = "MUTUAL FUND"
                    # mf_holdings uses 'fund' or 'tradingsymbol'
                    if "tradingsymbol" not in mf and "fund" in mf:
                        mf["tradingsymbol"] = mf["fund"]
                raw.extend(mf_raw)
            except Exception as e:
                logger.warning(f"Failed to fetch MF holdings: {e}")
        except Exception as e:
            raise RuntimeError(f"Kite get_holdings failed: {e}") from e

        # Fetch MF instruments to map ISIN to actual names
        mf_name_map = {}
        try:
            mf_inst = kite.mf_instruments()
            for inst in mf_inst:
                if "tradingsymbol" in inst and "name" in inst:
                    mf_name_map[inst["tradingsymbol"]] = inst["name"]
        except Exception as e:
            logger.error(f"Failed to fetch MF instruments: {e}")

        results = []
        for h in raw:
            quantity = float(h.get("quantity", 0))
            avg_cost = float(h.get("average_price", 0))
            ltp = float(h.get("last_price", 0))
            current_value = quantity * ltp
            invested_value = quantity * avg_cost
            pnl = current_value - invested_value
            pnl_pct = (pnl / invested_value * 100) if invested_value else 0.0

            ticker = h.get("tradingsymbol", "")
            asset_class = "mf" if h.get("instrument_type") == "MUTUAL FUND" else _classify_instrument(ticker, h.get("instrument_type", ""))
            
            asset_name = mf_name_map.get(ticker, ticker) if asset_class == "mf" else ticker

            results.append(HoldingCreate(
                id=str(uuid.uuid4()),
                asset_name=asset_name,
                ticker=ticker,
                asset_class=asset_class,
                sub_class=_sub_class(ticker, asset_class),
                source="kite",
                platform="Zerodha",
                quantity=quantity,
                avg_cost=avg_cost,
                current_price=ltp,
                current_value=current_value,
                invested_value=invested_value,
                unrealized_pnl=pnl,
                unrealized_pnl_pct=pnl_pct,
                sector=_sector_for(ticker),
            ))
        return results

    def get_positions(self) -> list[dict]:
        kite = self._get_kite()
        if kite is None:
            return []
        try:
            pos = kite.positions()
            return pos.get("net", [])
        except Exception as e:
            logger.error(f"Kite get_positions failed: {e}")
            return []

    def get_portfolio_margins(self) -> dict:
        kite = self._get_kite()
        if kite is None:
            return {}
        try:
            return kite.margins()
        except Exception as e:
            logger.error(f"Kite get_margins failed: {e}")
            return {}


def _classify_instrument(ticker: str, instrument_type: str) -> str:
    ticker_upper = ticker.upper()
    etf_suffixes = ("BEES", "ETF", "NIFTY", "GOLD", "LIQUID", "JUNIOR", "MOM100", "ICICIB22")
    if any(ticker_upper.endswith(s) or s in ticker_upper for s in etf_suffixes):
        if "GOLD" in ticker_upper:
            return "gold"
        if "LIQUID" in ticker_upper:
            return "cash"
        return "etf"
    if instrument_type.upper() in ("EQ", "BE"):
        return "equity"
    return "equity"


def _sub_class(ticker: str, asset_class: str) -> str | None:
    ticker_upper = ticker.upper()
    if "NIFTYBEES" in ticker_upper or "SETFNIF50" in ticker_upper:
        return "large_cap"
    if "JUNIORBEES" in ticker_upper or "MOM100" in ticker_upper:
        return "mid_small_cap"
    if "GOLDBEES" in ticker_upper:
        return "gold_etf"
    if "LIQUIDBEES" in ticker_upper:
        return "liquid"
    if "ICICIB22" in ticker_upper:
        return "international"
    return None


def _sector_for(ticker: str) -> str | None:
    mapping = {
        "BANKBEES": "Banking",
        "PSUBNKBEES": "PSU Banking",
        "ITBEES": "IT",
        "PHARMABEES": "Pharma",
        "INFRABEES": "Infrastructure",
        "NIFTYBEES": "Large Cap Index",
        "SETFNIF50": "Large Cap Index",
        "JUNIORBEES": "Mid Cap Index",
        "MOM100": "Momentum",
        "GOLDBEES": "Gold",
        "LIQUIDBEES": "Liquid",
        "ICICIB22": "International",
    }
    return mapping.get(ticker.upper())


def _upsert_env_var(key: str, value: str) -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return
    lines = env_path.read_text().splitlines()
    new_line = f"{key}={value}"
    replaced = False
    updated_lines: list[str] = []
    for line in lines:
        if line.strip().startswith(f"{key}="):
            updated_lines.append(new_line)
            replaced = True
        else:
            updated_lines.append(line)
    if not replaced:
        updated_lines.append(new_line)
    env_path.write_text("\n".join(updated_lines) + "\n")


def _parse_session_expiry(login_time) -> datetime | None:
    if isinstance(login_time, datetime):
        return login_time
    if isinstance(login_time, str):
        try:
            return datetime.fromisoformat(login_time.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None
