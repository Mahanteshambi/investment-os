import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SECTORS = [
    {"etf": "CPSEETF",    "token": 595969,    "sector": "PSU/CPSE"},
    {"etf": "PHARMABEES", "token": 1273089,   "sector": "Pharma"},
    {"etf": "MODEFENCE",  "token": 6385665,   "sector": "Defence"},
    {"etf": "METALIETF",  "token": 6364417,   "sector": "Metal"},
    {"etf": "ENERGY",     "token": 194503681, "sector": "Energy"},
    {"etf": "INFRABEES",  "token": 5138433,   "sector": "Infrastructure"},
    {"etf": "AUTOBEES",   "token": 2017281,   "sector": "Auto"},
    {"etf": "PSUBNKBEES", "token": 3848193,   "sector": "PSU Banking"},
    {"etf": "MOREALTY",   "token": 5935105,   "sector": "Realty"},
    {"etf": "BANKBEES",   "token": 2928385,   "sector": "Banking"},
    {"etf": "BFSI",       "token": 1336321,   "sector": "BFSI"},
    {"etf": "ITBEES",     "token": 4885505,   "sector": "IT"},
]


def _json_path() -> Path:
    default = Path(__file__).resolve().parents[3] / "sector_rotation.json"
    return Path(os.getenv("SECTOR_ROTATION_JSON_PATH", str(default)))


def load() -> dict:
    p = _json_path()
    if not p.exists():
        raise FileNotFoundError(f"sector_rotation.json not found at {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def _save(data: dict) -> None:
    _json_path().write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _compute_rsi(closes: list[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    ag = sum(gains[:period]) / period
    al = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        ag = (ag * (period - 1) + gains[i]) / period
        al = (al * (period - 1) + losses[i]) / period
    if al == 0:
        return 100.0
    return round(100 - 100 / (1 + ag / al), 1)


def _tech_score(vs200: Optional[float], vs50: float, rsi: float, w52: float, volr: float) -> float:
    s = 0.0
    if vs200 is None:       s += 1.5
    elif vs200 >= 5:        s += 3.0
    elif vs200 >= 2:        s += 2.5
    elif vs200 >= 0:        s += 2.0
    elif vs200 >= -2:       s += 1.0
    elif vs200 >= -5:       s += 0.5

    if   vs50 >= 2:         s += 2.0
    elif vs50 >= 0:         s += 1.5
    elif vs50 >= -2:        s += 0.5

    if   rsi >= 60:         s += 2.0
    elif rsi >= 50:         s += 1.5
    elif rsi >= 40:         s += 1.0
    elif rsi >= 30:         s += 0.5

    if   w52 >= 80:         s += 2.0
    elif w52 >= 60:         s += 1.5
    elif w52 >= 40:         s += 1.0
    elif w52 >= 25:         s += 0.5

    if   volr >= 1.2:       s += 1.0
    elif volr >= 0.8:       s += 0.5

    return round(s, 1)


def _decision(composite: float, existing_decision: str) -> str:
    if existing_decision == "EXITED":
        return "EXITED"
    if composite >= 7.0:
        return "BUY"
    if composite >= 5.0:
        return "HOLD"
    return "AVOID"


def sync_technical_scores(kite_service) -> dict:
    """Fetch fresh OHLCV from Kite, recompute technical scores, preserve qualitative scores."""
    data = load()

    existing: dict[str, dict] = {
        s["etf"].replace("NSE:", ""): s
        for s in data["current_month"]["scores"]
    }

    from_date = (datetime.now() - timedelta(days=410)).strftime("%Y-%m-%d 09:15:00")
    to_date = datetime.now().strftime("%Y-%m-%d 15:30:00")

    updated: list[dict] = []
    errors: list[str] = []

    for info in SECTORS:
        etf = info["etf"]
        token = info["token"]
        prev = existing.get(etf, {})

        try:
            candles = kite_service.get_historical_data(token, from_date, to_date, "day")
            closes = [float(c["close"]) for c in candles]
            volumes = [float(c["volume"]) for c in candles]

            if len(closes) < 2:
                if prev:
                    updated.append(prev)
                continue

            price = closes[-1]

            if len(closes) >= 200:
                dma200 = sum(closes[-200:]) / 200
                vs200 = (price / dma200 - 1) * 100
                dma200_str = (
                    f"ABOVE 200-DMA ~{dma200:.2f} (+{vs200:.1f}%)"
                    if vs200 >= 0
                    else f"BELOW 200-DMA ~{dma200:.2f} ({vs200:.1f}%)"
                )
            else:
                vs200 = None
                dma200_str = f"N/A — insufficient history ({len(closes)} candles)"

            n50 = min(50, len(closes))
            dma50 = sum(closes[-n50:]) / n50
            vs50 = (price / dma50 - 1) * 100
            dma50_str = (
                f"ABOVE 50-DMA ~{dma50:.2f} (+{vs50:.1f}%)"
                if vs50 >= 0
                else f"BELOW 50-DMA ~{dma50:.2f} ({vs50:.1f}%)"
            )

            rsi = _compute_rsi(closes)

            period = closes[-252:] if len(closes) >= 252 else closes
            lo, hi = min(period), max(period)
            w52 = ((price - lo) / (hi - lo) * 100) if hi > lo else 50.0

            n20 = min(20, len(volumes))
            n60 = min(60, len(volumes))
            vols20 = sum(volumes[-n20:]) / n20
            vols60 = sum(volumes[-n60:]) / n60
            volr = vols20 / vols60 if vols60 > 0 else 1.0

            tech = _tech_score(vs200, vs50, rsi, w52, volr)
            fund = prev.get("fundamental_score", 5.0)
            fii = prev.get("fii_dii_score", 5.0)
            composite = round(tech * 0.4 + fund * 0.3 + fii * 0.3, 1)

            updated.append({
                "rank": 0,
                "sector": info["sector"],
                "etf": f"NSE:{etf}",
                "token": token,
                "current_price": round(price, 2),
                "technical_score": tech,
                "fundamental_score": fund,
                "fii_dii_score": fii,
                "composite_score": composite,
                "decision": _decision(composite, prev.get("decision", "")),
                "monthly_allocation_inr": prev.get("monthly_allocation_inr", 0),
                "technical_detail": {
                    "price_vs_200dma": dma200_str,
                    "price_vs_50dma": dma50_str,
                    "rsi14": rsi,
                    "52w_position_pct": round(w52, 1),
                    "vol_ratio_20d_60d": round(volr, 2),
                },
                "notes": prev.get("notes", f"Technical refresh {datetime.now().strftime('%Y-%m-%d')}"),
            })

        except Exception as e:
            logger.error(f"Failed to refresh {etf}: {e}")
            errors.append(f"{etf}: {e}")
            if prev:
                updated.append(prev)

    updated.sort(key=lambda x: -x["composite_score"])
    for i, s in enumerate(updated):
        s["rank"] = i + 1

    active_etf = data["current_month"]["active_sector_etf"]
    active_score = next(
        (s["composite_score"] for s in updated if s["etf"] == active_etf),
        data["current_month"].get("active_sector_score", 0),
    )

    data["current_month"]["scores"] = updated
    data["current_month"]["generated_date"] = datetime.now().strftime("%Y-%m-%d")
    data["current_month"]["active_sector_score"] = active_score
    data["_last_technical_sync"] = datetime.now().isoformat()
    data["_sync_errors"] = errors

    _save(data)
    return data
