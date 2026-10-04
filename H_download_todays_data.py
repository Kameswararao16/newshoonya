from datetime import datetime, timedelta
import pandas as pd
import os
import json
import yaml

from api_helper import NorenApiPy
#==========================
OUTPUT_FILE = "Today_OHLC.csv"

# Remove existing output file
if os.path.exists(OUTPUT_FILE):
    os.remove(OUTPUT_FILE)
# =========================
# LOGIN
# =========================
api = NorenApiPy()

with open("cred.yml") as f:
    cred = yaml.load(f, Loader=yaml.FullLoader)

loginstatus = api.injectOAuthHeader(
    cred["Access_token"],
    cred["UID"],
    cred["Account_ID"]
)

if loginstatus is None:
    print("Login failed")
    exit()

print("API connected")


# =========================
# SETTINGS
# =========================
DATA_FOLDER = "nifty100_data"

n100 = pd.read_csv("NIFTY100_Tokens_org.csv")
NIFTY100 = n100.to_dict("records")

# =========================
# RUN DOWNLOAD
# =========================

now = datetime.now()

starttime = int(
    now.replace(
        year=2026,
        month=10,
        day=1,
        hour=9,
        minute=15,
        second=0,
        microsecond=0
    ).timestamp()
)

print(f"starttime: {starttime} ({datetime.fromtimestamp(starttime)})")
#--------------------------
for stock in NIFTY100:

    symbol = stock["Symbol"]
    token = stock["Token"]

    try:
        print(f"Downloading {symbol} {token}")

        candles = api.get_time_price_series(
            exchange="NSE",
            token=str(token),
            starttime=starttime,
            # endtime=int(now.timestamp()),
            interval=240
        )

        if not candles:
            print(f"No data for {symbol}")
            continue

        # Convert JSON strings (if required)
        candles = [
            json.loads(x) if isinstance(x, str) else x
            for x in candles
        ]

        df = pd.DataFrame(candles)

        df = df.rename(columns={
            "time": "Date",
            "into": "Open",
            "inth": "High",
            "intl": "Low",
            "intc": "Close"
        })

        df["Date"] = pd.to_datetime(df["Date"], dayfirst=True)

        for col in ["Open", "High", "Low", "Close"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # Shoonya generally returns latest candle first.
        # Uncomment the next line if required.
        df = df.iloc[::-1].reset_index(drop=True)

        row = {
            "Date": df.iloc[0]["Date"].strftime("%Y-%m-%d"),
            "Symbol": symbol,
            "Open": df.iloc[0]["Open"],
            "High": df["High"].max(),
            "Low": df["Low"].min(),
            "Close": df.iloc[-1]["Close"],
        }

        pd.DataFrame([row]).to_csv(
            OUTPUT_FILE,
            mode="a",
            header=not os.path.exists(OUTPUT_FILE),
            index=False
        )

        print(
            f"{symbol}: "
            f"O={row['Open']} "
            f"H={row['High']} "
            f"L={row['Low']} "
            f"C={row['Close']}"
        )

    except Exception as e:
        print(f"{symbol}: {e}")

print(f"\nSaved OHLC data to {OUTPUT_FILE}")

print("DOWNLOAD COMPLETE")