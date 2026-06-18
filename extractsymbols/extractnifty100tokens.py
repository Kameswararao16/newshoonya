import pandas as pd

# Nifty 100 symbols
NIFTY100 = [
    "ADANIENT",
    "ADANIPORTS",
    "APOLLOHOSP",
    "ASIANPAINT",
    "AXISBANK",
    "BAJAJ-AUTO",
    "BAJAJFINSV",
    "BAJFINANCE",
    "BEL",
    "BHARTIARTL",
    "BPCL",
    "BRITANNIA",
    "CIPLA",
    "COALINDIA",
    "DRREDDY",
    "EICHERMOT",
    "GRASIM",
    "HCLTECH",
    "HDFCBANK",
    "HDFCLIFE",
    "HEROMOTOCO",
    "HINDALCO",
    "HINDUNILVR",
    "ICICIBANK",
    "INDUSINDBK",
    "INFY",
    "ITC",
    "JIOFIN",
    "JSWSTEEL",
    "KOTAKBANK",
    "LT",
    "LTIM",
    "M&M",
    "MARUTI",
    "NESTLEIND",
    "NTPC",
    "ONGC",
    "POWERGRID",
    "RELIANCE",
    "SBILIFE",
    "SBIN",
    "SHRIRAMFIN",
    "SUNPHARMA",
    "TATACONSUM",
    "TATAMOTORS",
    "TATASTEEL",
    "TCS",
    "TECHM",
    "TITAN",
    "TRENT",
    "ULTRACEMCO",
    "WIPRO",
    "ZYDUSLIFE"
    # add remaining Nifty100 symbols
]


# Read NSE symbol master
df = pd.read_csv("NSEsymbols.csv")

# Filter NSE Equity
df = df[
    (df["Exchange"] == "NSE") &
    (df["Instrument"].str.contains("EQ", na=False))
]


# Keep only Nifty100
nifty100 = df[
    df["Symbol"].isin(NIFTY100)
]


# Select required columns
output = nifty100[
    [
        "Symbol",
        "TradingSymbol",
        "Token",
        "LotSize",
        "TickSize"
    ]
]


# Save
output.to_csv(
    "NIFTY100_Tokens.csv",
    index=False
)

print(
    f"Extracted {len(output)} Nifty100 symbols"
)

print(output.head())