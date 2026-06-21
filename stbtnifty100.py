from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import sendtelegram as tg
import os
from datetime import datetime, timedelta
#=====================================================
from api_helper import NorenApiPy, get_time
import logging
import yaml
import time
import json
#=====================================================
logging.basicConfig(level=logging.DEBUG)
pd.set_option("display.max_columns", None)
pd.set_option("display.width", None)

api = NorenApiPy()
#yaml for parameters
with open('cred.yml') as f:
    cred = yaml.load(f, Loader=yaml.FullLoader)
    print(cred)
loginstatus = api.injectOAuthHeader(cred['Access_token'],cred['UID'],cred['Account_ID'])
if loginstatus is not None:
    print("OAuth header injected successfully.")
else:
    print("Failed to inject OAuth header. Check credentials and try again.")
    exit(1)

# =====================================================
# NIFTY 100 SYMBOLS
# =====================================================
DATA_FOLDER = "nifty100_data"
# Read saved Nifty100 token file
n100 = pd.read_csv("NIFTY100_Tokens.csv")
# Store into NIFTY100 variable
NIFTY100 = n100.to_dict("records")
# =====================================================
# WICK LOGIC
# =====================================================
def add_wick_signal(df):
    print("Calculating wick signals...")
    total_range = df["High"] - df["Low"]

    upper_wick = df["High"] - df[["Open", "Close"]].max(axis=1)
    lower_wick = df[["Open", "Close"]].min(axis=1) - df["Low"]

    upper_pct = upper_wick / total_range
    lower_pct = lower_wick / total_range

    prev_high = df["High"].shift(1)
    prev_low = df["Low"].shift(1)

    is_green = df["Close"] > df["Open"]
    is_red = df["Close"] < df["Open"]

    df["WickSignal"] = np.select(
        [
            (lower_pct > 0.40)
            & (upper_pct < 0.20)
            & (df["Low"] < prev_low)
            & is_green,

            (upper_pct > 0.40)
            & (lower_pct < 0.20)
            & (df["High"] > prev_high)
            & is_red,
        ],
        ["Bullish", "Bearish"],
        default="Neutral",
    )

    return df


# =====================================================
# ENGULF LOGIC
# =====================================================
def engulf_wick_reference(df):
    print("Calculating engulf signals...")
    engulf_type = []

    for i in range(len(df)):

        if i < 1:
            engulf_type.append("Neutral")
            continue

        ref = df.iloc[i - 1]
        today = df.iloc[i]

        bullish_engulf = (
            (today.Close > today.Open)
            and (today.Open < min(ref.Open, ref.Close))
            and (today.Close > max(ref.Open, ref.Close))
        )

        bearish_engulf = (
            (today.Close < today.Open)
            and (today.Open > max(ref.Open, ref.Close))
            and (today.Close < min(ref.Open, ref.Close))
        )

        if bullish_engulf:
            engulf_type.append("Bullish")

        elif bearish_engulf:
            engulf_type.append("Bearish")

        else:
            engulf_type.append("Neutral")

    return pd.Series(engulf_type, index=df.index)

#==========================================================
# RANGE POSITION LOGIC
#==========================================================
def add_14day_range_position(df):
    print("Calculating 14-day range position...")
    # Previous 14 trading days excluding current day
    df["RangeHigh14"] = (
        df["High"]
        .shift(1)
        .rolling(14)
        .max()
    )

    df["RangeLow14"] = (
        df["Low"]
        .shift(1)
        .rolling(14)
        .min()
    )

    range_size = df["RangeHigh14"] - df["RangeLow14"]

    # Avoid divide-by-zero
    df["RangePct"] = np.where(
        range_size > 0,
        (df["Close"] - df["RangeLow14"]) / range_size,
        np.nan
    )

    df["RangeZone"] = np.select(
        [
            df["RangePct"] <= 0,
            (df["RangePct"] > 0) & (df["RangePct"] <= 0.25),
            (df["RangePct"] > 0.25) & (df["RangePct"] <= 0.50),
            (df["RangePct"] > 0.50) & (df["RangePct"] <= 0.75),
            (df["RangePct"] > 0.75) & (df["RangePct"] <= 1),
            df["RangePct"] > 1
        ],
        [
            "LOW-OUT",
            "LOW",
            "MID-LOW",
            "MID-HIGH",
            "HIGH",
            "HIGH-OUT"
        ],
        default="NA"
    )

    return df

# =====================================================
# 14-CANDLE TREND
# =====================================================
def add_14day_trend(df):

    print("Calculating 14-day trend...")

    trend_high = (
        df["High"]
        .shift(1)
        .rolling(14)
        .max()
    )

    trend_low = (
        df["Low"]
        .shift(1)
        .rolling(14)
        .min()
    )

    trend_mid = (trend_high + trend_low) / 2

    close_14ago = df["Close"].shift(14)

    df["Trend"] = np.select(
        [
            (df["Close"] > trend_mid) &
            (df["Close"] > close_14ago),

            (df["Close"] < trend_mid) &
            (df["Close"] < close_14ago)
        ],
        [
            "Uptrend",
            "Downtrend"
        ],
        default="Sideways"
    )

    return df

# =====================================================
# FINAL SIGNAL
# =====================================================
def generate_signals(df):
    print("Generating final signals...")
    # print(f"Generating signals for {df.index[-1].date()}")
    df["FinalSignal"] = "Neutral"
    df["TriggerLogic"] = ""

    for i in range(len(df)):

        wick = df["WickSignal"].iloc[i]
        engulf = df["EngulfType"].iloc[i]

        if wick != "Neutral":

            df.at[df.index[i], "FinalSignal"] = wick
            df.at[df.index[i], "TriggerLogic"] = "Wick"

        elif engulf == "Bullish":

            df.at[df.index[i], "FinalSignal"] = "Bullish"
            df.at[df.index[i], "TriggerLogic"] = "Bullish Engulf"

        elif engulf == "Bearish":

            df.at[df.index[i], "FinalSignal"] = "Bearish"
            df.at[df.index[i], "TriggerLogic"] = "Bearish Engulf"

    return df


# =====================================================
# SHOONYA DATA DOWNLOAD
# =====================================================
from datetime import datetime, timedelta
import json
import os
import pandas as pd


def get_processing_data(stock):
    symbol = stock["Symbol"]
    tradingsymbol = stock["TradingSymbol"]
    token = str(stock["Token"])

    csv_file = os.path.join(DATA_FOLDER, f"{symbol}.csv")

    hist = pd.DataFrame()

    # -----------------------------
    # Load existing cache
    # -----------------------------
    if os.path.exists(csv_file):
        hist = pd.read_csv(csv_file)

        if not hist.empty:
            hist["Date"] = pd.to_datetime(hist["Date"])

            hist = (
                hist
                .sort_values("Date")
                .tail(60)
            )

            latest_date = hist["Date"].max().date()
            today = datetime.now().date() - timedelta(days=1) # till yesterday's data is available

            print(
                f"{symbol}: latest cached date = {latest_date}, today = {today}"
            )

            # Skip Shoonya call if already updated today
            if latest_date >= today:
                print(
                    f"{symbol}: already updated today, using cached data"
                )
                return hist

            print(
                f"Loaded historical data for {symbol} with {len(hist)} rows."
            )

    # -----------------------------
    # Pull fresh data from Shoonya
    # -----------------------------
    end_time = int(datetime.now().timestamp())

    start_time = int(
        (datetime.now() - timedelta(days=5))
        .timestamp()
    )

    print(
        f"Fetching Shoonya data for {symbol}"
    )
    print(
        f"start_time: {datetime.fromtimestamp(start_time)}, "
        f"end_time: {datetime.fromtimestamp(end_time)}"
    )

    candles = api.get_daily_price_series(
        exchange="NSE",
        tradingsymbol=tradingsymbol,
        startdate=start_time,
        enddate=end_time
    )

    if not candles:
        print(f"{symbol}: No candles returned")

        if not hist.empty:
            return hist

        return None

    # -----------------------------
    # Convert Shoonya response
    # -----------------------------
    candles = [json.loads(x) for x in candles]

    df = pd.DataFrame(candles)

    df = df.rename(
        columns={
            "time": "Date",
            "into": "Open",
            "inth": "High",
            "intl": "Low",
            "intc": "Close",
            "intv": "Volume"
        }
    )

    df["Date"] = pd.to_datetime(df["Date"])

    for col in [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume"
    ]:
        df[col] = pd.to_numeric(
            df[col],
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

    # -----------------------------
    # Merge old + new
    # -----------------------------
    if not hist.empty:
        df = pd.concat(
            [hist, df],
            ignore_index=True
        )

    df = (
        df
        .drop_duplicates(
            subset=["Date"],
            keep="last"
        )
        .sort_values("Date")
        .tail(60)
        .reset_index(drop=True)
    )

    # -----------------------------
    # Save cache
    # -----------------------------
    os.makedirs(
        DATA_FOLDER,
        exist_ok=True
    )

    df.to_csv(
        csv_file,
        index=False
    )

    print(
        f"{symbol}: saved {len(df)} candles"
    )

    return df


# =====================================================
# PROCESS
# =====================================================

total_signals = 0

print(os.getcwd())

for stock in NIFTY100:

    try:

        ticker = stock["Symbol"]
        df = get_processing_data(stock)
        # # Wait 1 second
        # time.sleep(1)
        print(f"\nProcessing {ticker} with {len(df)} rows of data...")

        if df is None:
            continue

        print(f"Data for {ticker} loaded successfully with {len(df)} rows.")
        df = df.dropna()
        print(f"Data for {ticker} after dropping {ticker} has {len(df)} rows.")
        if len(df) < 1:
            continue
        print(f"Data for {ticker} is ready for signal generation.")
        # Get trend & range position
        df = add_14day_trend(df)
        # print(f"df: {df.tail()}")
        df = add_14day_range_position(df)
        # print(f"df: {df.tail()}")
        # Get wick signals
        df = add_wick_signal(df)
        # print(f"df: {df.tail()}")
        # Get engulf signals
        df["EngulfType"] = engulf_wick_reference(df)
        # print(f"df: {df.tail()}")
        # Generate final signals
        df = generate_signals(df)
        # print(f"df: {df.tail()}")
        latest = df.iloc[-1]
        range_zone = latest["RangeZone"]
        # print(f"last row: {latest.to_dict()}")
        if latest["FinalSignal"] == "Neutral":
            continue

        signal = latest["FinalSignal"]
        entry = round(float(latest["Close"]), 2)

        if signal == "Bullish":
            sl = round(float(latest["Low"]), 2)
            risk = entry - sl
            target = round(entry + (risk * 2), 2)
            trade_type = "LONG"
        else:
            sl = round(float(latest["High"]), 2)
            risk = sl - entry
            target = round(entry - (risk * 2), 2)
            trade_type = "SHORT"
        print(f"Signal: {signal}, Entry: {entry}, SL: {sl}, Target: {target}, RangeZone: {range_zone}")
        # print(latest)
        print(df)
        # tg.send_telegram_alert(
        #     symbol=ticker,
        #     signal=signal,
        #     entry_price=entry,
        #     stop_loss=sl,
        #     target_price=target,
        #     logic=f"{latest['TriggerLogic']} | 14D Range:  {range_zone}",
        #     buy_type=trade_type,
        #     entry_time=str(latest['Date'].date())
        # )

        print(
            f"{ticker} | "
            f"{str(latest['Date'].date())} | "
            f"{signal} | "
            f"{latest['TriggerLogic']} | "  
            f"{range_zone}"
        )

    except Exception as e:
        print(f"Error processing...")
        print(f"{ticker}: {e}")

print("\n================================")
# print("TOTAL SIGNALS:", total_signals)
print("SCAN COMPLETED")
print("================================")