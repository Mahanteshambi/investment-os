import os
import json
import logging
import asyncio
import urllib.parse
from datetime import datetime, date
from typing import Optional
from dotenv import load_dotenv
load_dotenv()

from pydantic import BaseModel, Field

# We import crawl4ai modules. Note: running this requires PLAYWRIGHT_BROWSERS_PATH or playwright install
from crawl4ai import AsyncWebCrawler
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

class MFSectorWeightModel(BaseModel):
    sector_name: str
    weight_pct: float

class MFStockHoldingModel(BaseModel):
    stock_name: str
    weight_pct: float

class MFIntelligenceData(BaseModel):
    fund_name: str
    category: Optional[str] = None
    sub_category: Optional[str] = None
    objective: Optional[str] = None
    fund_manager: Optional[str] = None
    benchmark: Optional[str] = None
    expense_ratio: Optional[float] = None
    aum_cr: Optional[float] = None
    equity_pct: Optional[float] = None
    debt_pct: Optional[float] = None
    cash_pct: Optional[float] = None
    return_1y: Optional[float] = None
    return_3y: Optional[float] = None
    return_5y: Optional[float] = None
    return_inception: Optional[float] = None
    benchmark_return_1y: Optional[float] = None
    benchmark_return_3y: Optional[float] = None
    benchmark_return_5y: Optional[float] = None
    benchmark_return_inception: Optional[float] = None
    category_return_1y: Optional[float] = None
    category_return_3y: Optional[float] = None
    category_return_5y: Optional[float] = None
    sector_weights: list[MFSectorWeightModel] = []
    stock_holdings: list[MFStockHoldingModel] = []


def _get_search_url(fund_name: str) -> str:
    """Fallback search approach. ET Money often has very predictable paths or we use DuckDuckGo."""
    query = urllib.parse.quote_plus(f"{fund_name} mutual fund etmoney")
    return f"https://html.duckduckgo.com/html/?q={query}"


async def extract_mf_intelligence(fund_name: str) -> Optional[MFIntelligenceData]:
    """Uses crawl4ai with Gemini to extract structured mutual fund data."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY is not set. Cannot run MF Intelligence extraction.")
        return None

    # Step 1: Use DuckDuckGo to find the ET Money or Moneycontrol URL for the fund
    search_url = _get_search_url(fund_name)
    
    # We will instruct the LLM to extract data from whatever page it lands on.
    # We will use ET Money or Moneycontrol page text.
    instruction = (
        "You are a financial data extractor. I am providing you with the text of a Mutual Fund details page (like Moneycontrol or ET Money). "
        "Extract all the requested fields into the specified JSON schema. "
        "For percentages, use decimal formats (e.g., 45.5 for 45.5%). "
        "For AUM, convert it to Crores (e.g., if it says 5000 Cr, put 5000). "
        "If a field is missing, set it to null. "
        "Extract the top 5-10 stock holdings and the top sector weights."
    )

    try:
        async with AsyncWebCrawler(verbose=True) as crawler:
            search_result = await crawler.arun(url=search_url)
            real_url = None
            if search_result.html:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(search_result.html, "html.parser")
                for a in soup.find_all("a", class_="result__url"):
                    href = a.get("href", "")
                    decoded_href = urllib.parse.unquote(href)
                    if "etmoney.com/mutual-funds" in decoded_href or "moneycontrol.com/mutual-funds" in decoded_href:
                        if "uddg=" in decoded_href:
                            real_url = decoded_href.split("uddg=")[1].split("&")[0]
                        else:
                            real_url = "https:" + href if href.startswith("//") else href
                        break

            if not real_url:
                logger.error(f"Could not find a valid Mutual Fund URL for: {fund_name}")
                return None

            logger.info(f"Scraping MF Intelligence from: {real_url}")
            
            result = await crawler.arun(
                url=real_url,
                bypass_cache=True
            )
            
            if result.markdown:
                client = genai.Client(api_key=api_key)
                # Ensure the prompt uses the raw schema directly
                schema = MFIntelligenceData.model_json_schema()
                prompt = instruction + "\n\nMarkdown Content:\n" + result.markdown[:50000] + "\n\nReturn EXACTLY a JSON object matching this schema: " + json.dumps(schema)
                
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.0
                    )
                )
                
                data_dict = json.loads(response.text)
                if isinstance(data_dict, list) and len(data_dict) > 0:
                    data_dict = data_dict[0]
                
                return MFIntelligenceData(**data_dict)
            else:
                logger.error(f"Crawl4AI returned empty markdown for {fund_name}.")
                return None
    except Exception as e:
        logger.error(f"Exception during MF Intelligence extraction: {e}")
        return None


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    async def test():
        res = await extract_mf_intelligence("Motilal Oswal Midcap Fund Direct Growth")
        if res:
            print(json.dumps(res.model_dump(), indent=2))
        else:
            print("Failed")
            
    asyncio.run(test())
