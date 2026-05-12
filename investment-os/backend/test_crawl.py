import asyncio, os
from crawl4ai import AsyncWebCrawler, LLMConfig
from crawl4ai.extraction_strategy import LLMExtractionStrategy
from dotenv import load_dotenv

load_dotenv()

async def run():
    async with AsyncWebCrawler() as crawler:
        res = await crawler.arun('https://www.etmoney.com/mutual-funds/motilal-oswal-elss-tax-saver-fund/28670')
        print('Markdown length:', len(res.markdown))
        print('Markdown preview:', res.markdown[:500])

if __name__ == '__main__':
    asyncio.run(run())
