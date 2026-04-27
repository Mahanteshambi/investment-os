import os
from kiteconnect import KiteConnect

api_key = os.getenv("KITE_API_KEY", "").strip()
access_token = os.getenv("KITE_ACCESS_TOKEN", "").strip()

if not api_key or not access_token:
    print("Missing kite credentials")
else:
    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)
    try:
        holdings = kite.holdings()
        print(f"Got {len(holdings)} holdings from Kite")
        mf_holdings = [h for h in holdings if h.get("instrument_type") == "MUTUAL FUND" or "MF" in h.get("instrument_type", "")]
        print(f"Got {len(mf_holdings)} mutual funds")
        if mf_holdings:
            print("First MF:", mf_holdings[0])
            print("Total MF Value:", sum(float(h.get('quantity', 0)) * float(h.get('last_price', 0)) for h in mf_holdings))
    except Exception as e:
        print(f"Error: {e}")
