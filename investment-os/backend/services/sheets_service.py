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
        results = []

        for sheet_name, config in SHEET_CONFIGS.items():
            rows = self._read_sheet(sheet_name)
            for row in rows:
                asset_name = str(row.get("asset_name", "")).strip()
                if not asset_name:
                    continue

                asset_class = config["asset_class"] or str(row.get("asset_class", "equity")).strip()
                ticker = str(row.get("ticker", "")).strip() or None
                sub_class = str(row.get("sub_class", row.get("asset_type", ""))).strip() or None

                quantity = _to_float(row.get("quantity"))
                avg_cost = _to_float(row.get("avg_cost"))
                current_price = _to_float(row.get("current_price"))

                current_value = None
                invested_value = None
                pnl = None
                pnl_pct = None

                if quantity is not None and current_price is not None:
                    current_value = quantity * current_price
                if quantity is not None and avg_cost is not None:
                    invested_value = quantity * avg_cost
                if current_value is not None and invested_value is not None:
                    pnl = current_value - invested_value
                    pnl_pct = (pnl / invested_value * 100) if invested_value else 0.0

                results.append(HoldingCreate(
                    id=str(uuid.uuid4()),
                    asset_name=asset_name,
                    ticker=ticker,
                    asset_class=asset_class,
                    sub_class=sub_class,
                    source="sheets",
                    quantity=quantity,
                    avg_cost=avg_cost,
                    current_price=current_price,
                    current_value=current_value,
                    invested_value=invested_value,
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
