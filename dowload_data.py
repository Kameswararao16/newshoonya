from datetime import datetime, timedelta
import pandas as pd
import os
import json
import yaml

from api_helper import NorenApiPy


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

n100 = pd.read_csv("NIFTY100_Tokens.csv")
NIFTY100 = n100.to_dict("records")


# =========================
# DOWNLOAD FUNCTION
# =========================

def download_stock(stock):

    symbol = stock["Symbol"]
    tradingsymbol = stock["TradingSymbol"]
    print(f"Downloading {symbol} ({tradingsymbol})")
    csv_file = os.path.join(
        DATA_FOLDER,
        f"{symbol}.csv"
    )

    old = pd.DataFrame()


    # Load cache
    if os.path.exists(csv_file):

        old = pd.read_csv(csv_file)

        if not old.empty:

            old["Date"] = pd.to_datetime(old["Date"])

            old = (
                old
                .sort_values("Date")
                .tail(60)
            )

            latest = old["Date"].max().date()
            today = datetime.now().date() - timedelta(days=1)

            if latest >= today:

                print(
                    f"{symbol}: already updated"
                )
                return


    print(
        f"Downloading {symbol}"
    )

    # ret1 = api.searchscrip(
    #     exchange="NSE",
    #     searchtext=tradingsymbol
    # )

    # print(ret1)

    candles = api.get_daily_price_series(
        exchange="NSE",
        tradingsymbol=tradingsymbol,
        startdate=int(
            (datetime.now()-timedelta(days=5)).timestamp()
        ),
        enddate=int(
            datetime.now().timestamp()
        )
    )


    if not candles:
        print(
            f"No data {symbol}"
        )
        return


    candles = [
        json.loads(x)
        for x in candles
    ]


    df = pd.DataFrame(candles)


    df = df.rename(
        columns={
            "time":"Date",
            "into":"Open",
            "inth":"High",
            "intl":"Low",
            "intc":"Close",
            "intv":"Volume"
        }
    )


    df["Date"] = pd.to_datetime(
        df["Date"]
    )


    for c in [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume"
    ]:
        df[c] = pd.to_numeric(
            df[c],
            errors="coerce"
        )


    df = df[
        [
            "Date",
            "Open",
            "High",
            "Low",
            "Close",
            "Volume"
        ]
    ]


    if not old.empty:

        df = pd.concat(
            [
                old,
                df
            ]
        )


    df = (
        df
        .drop_duplicates(
            "Date",
            keep="last"
        )
        .sort_values("Date")
        .tail(60)
    )


    os.makedirs(
        DATA_FOLDER,
        exist_ok=True
    )


    df.to_csv(
        csv_file,
        index=False
    )


    print(
        f"{symbol}: saved {len(df)} rows"
    )



# =========================
# RUN DOWNLOAD
# =========================

for stock in NIFTY100:

    try:
        download_stock(stock)

    except Exception as e:

        print(
            stock["Symbol"],
            e
        )


print("DOWNLOAD COMPLETE")