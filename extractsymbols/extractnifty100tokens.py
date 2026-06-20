import pandas as pd

# Nifty 100 symbols
NIFTY100 = [
    "ABB",
"ADANIENSOL",
"ADANIENT",
"ADANIGREEN",
"ADANIPORTS",
"ADANIPOWER",
"AMBUJACEM",
"APOLLOHOSP",
"ASIANPAINT",
"DMART",
"AXISBANK",
"BAJAJ-AUTO",
"BAJFINANCE",
"BAJAJFINSV",
"BAJAJHLDNG",
"BANKBARODA",
"BEL",
"BPCL",
"BHARTIARTL",
"BRITANNIA",
"CANBK",
"CGPOWER",
"CHOLAFIN",
"CIPLA",
"COALINDIA",
"CONCOR",
"CUMMINSIND",
"DABUR",
"DIVISLAB",
"DLF",
"DRREDDY",
"EICHERMOT",
"ETERNAL",
"GAIL",
"GODREJCP",
"GRASIM",
"HAL",
"HCLTECH",
"HDFCBANK",
"HAVELLS",
"HEROMOTOCO",
"HINDALCO",
"HINDUNILVR",
"HYUNDAI",
"ICICIBANK",
"ICICIPRULI",
"INDHOTEL",
"IOC",
"IRFC",
"INDUSINDBK",
"NAUKRI",
"INFY",
"INDIGO",
"ITC",
"JINDALSTEL",
"JIOFIN",
"JSWSTEEL",
"KOTAKBANK",
"LT",
"LICHSGFIN",
"LTIM",
"LODHA",
"M&M",
"MANKIND",
"MARICO",
"MARUTI",
"MAXHEALTH",
"MOTHERSON",
"NESTLEIND",
"NHPC",
"NTPC",
"ONGC",
"PIDILITIND",
"PNB",
"POWERGRID",
"RECLTD",
"RELIANCE",
"SBILIFE",
"SHRIRAMFIN",
"SIEMENS",
"SRF",
"SBIN",
"SUNPHARMA",
"TCS",
"TATACONSUM",
"TATAMOTORS",
"TATAPOWER",
"TATASTEEL",
"TECHM",
"TITAN",
"TORNTPHARM",
"TRENT",
"TVSMOTOR",
"ULTRACEMCO",
"UNIONBANK",
"MCDOWELL-N",
"VBL",
"VEDL",
"WIPRO",
"ZYDUSLIFE"
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