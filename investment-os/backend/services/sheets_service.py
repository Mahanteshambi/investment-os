import logging
import os
import uuid
from typing import Any

from models.schemas import HoldingCreate

logger = logging.getLogger(__name__)

SHEET_CONFIGS = {
    "MutualFunds": {
        "asset_class": "mf",
        "columns": ["asset_name", "ticker", "quantity", "avg_cost", "current_price", "sub_class", "notes"],
    },
    "Gold": {
        "asset_class": "gold",
        "columns": ["asset_name", "asset_type", "quantity", "avg_cost", "current_price", "notes"],
    },
    "OtherAssets": {
        "asset_class": None,  # read from sheet column
        "columns": ["asset_name", "asset_class", "quantity", "avg_cost", "current_price", "notes"],
    },
}


class SheetsService:
    def __init__(self):
        self.credentials_path = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON", "")
        self.sheet_id = os.getenv("GOOGLE_SHEET_ID", "")
        self._client = None
        self._spreadsheet = None

    def _get_client(self):
        if not self.credentials_path:
            raise RuntimeError(
                "Google Sheets credentials path missing. Set GOOGLE_SHEETS_CREDENTIALS_JSON."
            )
        if self._client is None:
            try:
                import gspread
                from google.oauth2.service_account import Credentials
                scopes = [
                    "https://www.googleapis.com/auth/spreadsheets.readonly",
                    "https://www.googleapis.com/auth/drive.readonly",
                ]
                creds = Credentials.from_service_account_file(self.credentials_path, scopes=scopes)
                self._client = gspread.authorize(creds)
            except Exception as e:
                raise RuntimeError(f"Google Sheets auth failed: {e}") from e
        return self._client

    def _get_spreadsheet(self):
        if not self.sheet_id:
            raise RuntimeError("Google Sheet ID missing. Set GOOGLE_SHEET_ID.")
        if self._spreadsheet is None:
            client = self._get_client()
            try:
                self._spreadsheet = client.open_by_key(self.sheet_id)
            except Exception as e:
                raise RuntimeError(f"Failed to open spreadsheet {self.sheet_id}: {e}") from e
        return self._spreadsheet

    def _read_sheet(self, sheet_name: str) -> list[dict[str, Any]]:
        spreadsheet = self._get_spreadsheet()
        try:
            ws = spreadsheet.worksheet(sheet_name)
            return ws.get_all_records()
        except Exception as e:
            logger.warning(f"Sheet '{sheet_name}' not found or unreadable: {e}")
            return []

    def get_all_manual_holdings(self) -> list[HoldingCreate]:
        spreadsheet = self._get_spreadsheet()
        try:
            ws = spreadsheet.worksheet("Details")
            records = ws.get_all_values()
        except Exception as e:
            logger.error(f"Failed to read 'Details' sheet: {e}")
            return []

        results = []
        current_name = None
        current_country = None
        current_asset = None

        # Headers are at index 1, data starts at index 2
        for row in records[2:]:
            if not row or len(row) < 6:
                continue

            raw_asset = row[2].strip() if len(row) > 2 else ""
            raw_platform = row[3].strip() if len(row) > 3 else ""

            # If both Asset and Platform are blank on this specific row, it's a Total row. Skip it.
            if not raw_asset and not raw_platform:
                continue

            name = row[0].strip() if len(row) > 0 and row[0].strip() else current_name
            country = row[1].strip() if len(row) > 1 and row[1].strip() else current_country
            asset = raw_asset if raw_asset else current_asset
            
            current_name = name
            current_country = country
            current_asset = asset

            if current_name and current_name.lower() != "mahantesh":
                continue

            platform = raw_platform

            # Deduplication: Kite/Zerodha/Coin are handled by KiteService.
            # We now fetch Coin mutual funds via the kite.mf_holdings() API!
            if platform.lower() in ["kite", "zerodha", "coin"]:
                logger.info(f"Skipping live platform holding from sheet: {platform}")
                continue

            invested_str = row[4].replace(',', '').strip() if len(row) > 4 else ""
            current_str = row[5].replace(',', '').strip() if len(row) > 5 else ""

            invested = float(invested_str) if invested_str else 0.0
            current_val = float(current_str) if current_str else 0.0

            if invested == 0 and current_val == 0:
                continue

            pnl = current_val - invested
            pnl_pct = (pnl / invested * 100) if invested else 0.0

            # Map asset names to our internal classes
            a_lower = (asset or "").lower()
            asset_class = "equity"
            if "mutual" in a_lower:
                asset_class = "mf"
            elif "fd" in a_lower:
                asset_class = "fd"
            elif "ppf" in a_lower:
                asset_class = "ppf"
            elif "pf" in a_lower:
                asset_class = "pf"
            elif "rd" in a_lower:
                asset_class = "rd"
            elif "savings" in a_lower:
                asset_class = "savings"
            elif "cash" in a_lower:
                asset_class = "cash"
            elif "gold" in a_lower:
                asset_class = "gold"

            results.append(HoldingCreate(
                id=str(uuid.uuid4()),
                asset_name=f"{platform} {asset}".strip() if platform else asset,
                ticker=None,
                asset_class=asset_class,
                sub_class=None,
                source="sheets",
                platform=platform.strip() if platform else "Other",
                quantity=1.0,
                avg_cost=invested,
                current_price=current_val,
                current_value=current_val,
                invested_value=invested,
                unrealized_pnl=pnl,
                unrealized_pnl_pct=pnl_pct,
                sector=None,
            ))

        return results


def _to_float(val: Any) -> float | None:
    if val is None or val == "":
        return None
    try:
        return float(str(val).replace(",", ""))
    except (ValueError, TypeError):
        return None
