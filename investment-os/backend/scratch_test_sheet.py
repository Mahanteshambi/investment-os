import os
import sys

# Hack to load path and env
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()

from services.sheets_service import SheetsService

def test():
    try:
        svc = SheetsService()
        print(f"Using creds: {svc.credentials_path}")
        print(f"Using sheet id: {svc.sheet_id}")
        
        client = svc._get_client()
        print("Auth success!")
        
        try:
            doc = client.open_by_key(svc.sheet_id)
            print(f"Spreadsheet title: {doc.title}")
            for ws in doc.worksheets():
                print(f" - {ws.title}")
            
            # Read Details sheet using get_all_values
            details = doc.worksheet("Details")
            records = details.get_all_values()
            print(f"Found {len(records)} rows in Details sheet.")
            if len(records) > 0:
                for i in range(10, len(records)):
                    print(f"Row {i}: {records[i]}")
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"FAILED TO OPEN: {type(e).__name__} - {e}")
            
    except Exception as e:
        print(f"Init Error: {e}")

if __name__ == "__main__":
    test()
