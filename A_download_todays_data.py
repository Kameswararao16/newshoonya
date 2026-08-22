from datetime import datetime, timedelta
import pandas as pd
import os
import json
import yaml
import csv
import time

# =========================
# Input NIFTY stocks
# =========================
DATA_FOLDER = "nifty100_data_today"
NIFTY = pd.read_csv("NIFTY50_Tokens.csv")
NIFTY = NIFTY.to_dict("records")

# =========================
# DOWNLOAD FUNCTION
# =========================
def download_stock(stock, api, st, et):

    symbol = stock["Symbol"]
    tradingsymbol = stock["TradingSymbol"]
    token = stock["Token"]
    # print(f"Downloading {symbol} ({tradingsymbol}:{token})")

    # create folder
    os.makedirs(DATA_FOLDER, exist_ok=True)
    csv_file = os.path.join(DATA_FOLDER, f"{symbol}.csv")
    # print(f"File: {csv_file}")

    
    print(f"start time: {st}, end time: {et}")
    candles = api.get_time_price_series(
        exchange="NSE",
        token=str(token),
        starttime=int(st.timestamp()),
        endtime=int(et.timestamp()),
        interval=5
    )

    if not candles:
        print(f"No data for {symbol}")
        return

    # print(f"Candle: {candles} ")

    # read existing timestamps
    existing = set()
    if os.path.exists(csv_file):
        with open(csv_file, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing.add(row["Date"])

    # print(f"{symbol}: existing timestamps: {len(existing)}")
    new_rows = []
    for item in candles:
        if isinstance(item, str):
            candle = json.loads(item)
        else:
            candle = item
        row = [
            candle["time"],
            candle["into"],
            candle["inth"],
            candle["intl"],
            candle["intc"],
            candle["intv"]
        ]

        # skip duplicate
        if row[0] not in existing:
            new_rows.append(row)
            existing.add(row[0])
            
    # print(f"{symbol}: new candles: {len(new_rows)}")
    if not new_rows:
        print(f"{symbol}: no new candles")
        return

    file_exists = os.path.exists(csv_file)
    # print(f"{symbol}: file exists: {file_exists}")
    with open(
        csv_file,
        "a",
        newline=""
    ) as f:

        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "Date",
                "Open",
                "High",
                "Low",
                "Close",
                "Volume"
            ])

        writer.writerows(new_rows)

    # print(f"{symbol}: saved {len(new_rows)} candles")
    # print("File:", os.path.abspath(csv_file))


# =========================
# RUN DOWNLOAD
# =========================
def download_all_stocks(api):
    et = datetime.now().replace(second=0, microsecond=0)
    st = et - timedelta(minutes=5)
    print("waiting for 60seconds...")
    time.sleep(60) # Attimes, full 5-minutes candle is not formming correctly. So, wait for 60 seconds
    # st = datetime.now().replace(hour=9, minute=15, second=0, microsecond=0) - timedelta(minutes=5) # Only for testing purpose
    for stock in NIFTY:
        try:
            download_stock(stock, api, st, et)
        except Exception as e:
            print(stock["Symbol"], e)

    print("DOWNLOAD COMPLETE")

# #===================TEST===================================
# #login to API
# from api_helper import NorenApiPy

# api = NorenApiPy()

# with open("cred.yml") as f:
#     cred = yaml.load(f, Loader=yaml.FullLoader)

# loginstatus = api.injectOAuthHeader(
#     cred["Access_token"],
#     cred["UID"],
#     cred["Account_ID"]
# )

# if loginstatus is None:
#     print("Login failed")
#     exit()

# print("API connected")
# #=================================================
# download_all_stocks(api)