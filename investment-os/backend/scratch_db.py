import duckdb
conn = duckdb.connect('./data/investment_os.duckdb', read_only=True)
res = conn.execute("SELECT asset_name, asset_class, source, current_value, unrealized_pnl FROM holdings").fetchall()
import pandas as pd
df = pd.DataFrame(res, columns=["name", "class", "source", "current", "pnl"])
print(df.to_string())
print("Total Value:", df['current'].sum())
print("Total PNL:", df['pnl'].sum())

print("\n--- Day P&L logic ---")
# See if there is a day_pnl column
# DESCRIBE holdings;
desc = conn.execute("DESCRIBE holdings;").fetchall()
print(desc)
