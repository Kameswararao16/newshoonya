# process_data.py

import pandas as pd
import numpy as np
import os


# =====================================================
# SETTINGS
# =====================================================

DATA_FOLDER = "nifty100_data"

n100 = pd.read_csv(
    "NIFTY100_Tokens.csv"
)

NIFTY100 = n100.to_dict("records")

pd.set_option("display.max_columns", None)
pd.set_option("display.width", None)



# =====================================================
# WICK LOGIC
# =====================================================

def add_wick_signal(df):

    total_range = df["High"] - df["Low"]

    upper_wick = (
        df["High"]
        - df[["Open","Close"]]
        .max(axis=1)
    )

    lower_wick = (
        df[["Open","Close"]]
        .min(axis=1)
        - df["Low"]
    )


    upper_pct = upper_wick / total_range
    lower_pct = lower_wick / total_range


    prev_high = df["High"].shift(1)
    prev_low = df["Low"].shift(1)


    green = df["Close"] > df["Open"]
    red = df["Close"] < df["Open"]


    df["WickSignal"] = np.select(
        [

            (lower_pct > 0.40)
            &
            (upper_pct < 0.20)
            &
            (df["Low"] < prev_low)
            &
            green,


            (upper_pct > 0.40)
            &
            (lower_pct < 0.20)
            &
            (df["High"] > prev_high)
            &
            red

        ],

        [
            "Bullish",
            "Bearish"
        ],

        default="Neutral"
    )


    return df




# =====================================================
# ENGULFING
# =====================================================

def engulf_wick_reference(df):

    result = []


    for i in range(len(df)):


        if i == 0:
            result.append("Neutral")
            continue


        prev = df.iloc[i-1]
        cur = df.iloc[i]


        bullish = (
            cur.Close > cur.Open
            and
            cur.Open < min(prev.Open,prev.Close)
            and
            cur.Close > max(prev.Open,prev.Close)
        )


        bearish = (
            cur.Close < cur.Open
            and
            cur.Open > max(prev.Open,prev.Close)
            and
            cur.Close < min(prev.Open,prev.Close)
        )


        if bullish:
            result.append("Bullish")

        elif bearish:
            result.append("Bearish")

        else:
            result.append("Neutral")


    return pd.Series(
        result,
        index=df.index
    )




# =====================================================
# RANGE
# =====================================================

def add_14day_range_position(df):


    high14 = (
        df["High"]
        .shift(1)
        .rolling(14)
        .max()
    )


    low14 = (
        df["Low"]
        .shift(1)
        .rolling(14)
        .min()
    )


    size = high14-low14


    df["RangePct"] = np.where(
        size>0,
        (df["Close"]-low14)/size,
        np.nan
    )


    df["RangeZone"] = np.select(

        [

            df["RangePct"]<=0,

            df["RangePct"]<=0.25,

            df["RangePct"]<=0.50,

            df["RangePct"]<=0.75,

            df["RangePct"]<=1,

            df["RangePct"]>1

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
# TREND
# =====================================================

def add_14day_trend(df):


    high14 = (
        df["High"]
        .shift(1)
        .rolling(14)
        .max()
    )


    low14 = (
        df["Low"]
        .shift(1)
        .rolling(14)
        .min()
    )


    mid = (high14+low14)/2


    old_close = df["Close"].shift(14)


    df["Trend"] = np.select(

        [

            (df["Close"] > mid)
            &
            (df["Close"] > old_close),


            (df["Close"] < mid)
            &
            (df["Close"] < old_close)

        ],


        [

            "Uptrend",
            "Downtrend"

        ],

        default="Sideways"

    )


    return df


# =====================================================
# BULLISH TWEEZER BOTTOM
# =====================================================

def tweezers(df):

    result = []

    for i in range(len(df)):

        if i == 0:
            result.append("Neutral")
            continue


        prev = df.iloc[i-1]
        cur = df.iloc[i]


        same_low = (
            abs(prev.Low - cur.Low)
            <= (cur.Close * 0.001)
        )
        prev_red = prev.Close < prev.Open
        cur_green = cur.Close > cur.Open

        same_high = (
            abs(prev.High-cur.High)
            <= (cur.Close*0.001)
        )
        prev_green = prev.Close > prev.Open
        cur_red = cur.Close < cur.Open

        if same_low and prev_red and cur_green:
            result.append("Bullish")
        elif same_high and prev_green and cur_red:
            result.append("Bearish")
        else:
            result.append("Neutral")


    return pd.Series(
        result,
        index=df.index
    )


# =====================================================
# FINAL SIGNAL
# =====================================================

def generate_signals(df):

    df["FinalSignal"]="Neutral"
    df["TriggerLogic"]=""

    for i in range(len(df)):
        wick = df["WickSignal"].iloc[i]
        engulf = df["EngulfType"].iloc[i]
        tweezer = df["tweezer"].iloc[i]

        if wick != "Neutral":

            df.at[
                df.index[i],
                "FinalSignal"
            ] = wick

            df.at[
                df.index[i],
                "TriggerLogic"
            ] = "Wick"


        elif tweezer == "Bullish":

            df.at[
                df.index[i],
                "FinalSignal"
            ]="Bullish"

            df.at[
                df.index[i],
                "TriggerLogic"
            ]="Bullish Tweezer"


        elif tweezer == "Bearish":

            df.at[
                df.index[i],
                "FinalSignal"
            ]="Bearish"

            df.at[
                df.index[i],
                "TriggerLogic"
            ]="Bearish Tweezer"


        elif engulf=="Bullish":

            df.at[
                df.index[i],
                "FinalSignal"
            ]="Bullish"

            df.at[
                df.index[i],
                "TriggerLogic"
            ]="Bullish Engulf"


        elif engulf=="Bearish":

            df.at[
                df.index[i],
                "FinalSignal"
            ]="Bearish"

            df.at[
                df.index[i],
                "TriggerLogic"
            ]="Bearish Engulf"

    # print(f"======={stock['Symbol']}==================")
    # print(df)
    return df


# =====================================================
# PROCESS ALL STOCKS
# =====================================================


print("\nSTART SCAN\n")


for stock in NIFTY100:

    ticker = stock["Symbol"]

    try:

        file = os.path.join( DATA_FOLDER, ticker+".csv")
        if not os.path.exists(file):
            print(ticker, "missing data")
            continue

        df = pd.read_csv(file)
        df["Date"] = pd.to_datetime(df["Date"])
        df = (df.sort_values("Date").tail(60))

        if len(df)<20: 
            continue

        df = add_14day_trend(df)
        df = add_14day_range_position(df)
        df = add_wick_signal(df)
        df["EngulfType"] = engulf_wick_reference(df)
        df["tweezer"] = tweezers(df)
        df = generate_signals(df)

        last = df.iloc[-1]
        if last["FinalSignal"]=="Neutral":
            continue

        entry = round(float(last.Close), 2)

        if last.FinalSignal=="Bullish":
            sl = round(float(last.Low), 2)
            target = round(entry + (entry-sl)*2, 2)
            side="LONG"
        else:
            sl = round(float(last.High), 2)
            target = round( entry - (sl-entry)*2, 2)
            side="SHORT"

        print(
            ticker,
            "|",
            last.Date.date(),
            "|",
            side,
            "|",
            last.FinalSignal,
            "|",
            last.TriggerLogic,
            "| Entry:",
            entry,
            "| SL:",
            sl,
            "| Target:",
            target,
            "|",
            last.RangeZone
        )

    except Exception as e:
        print(ticker, e)


print("\n===================")
print("SCAN COMPLETED")
print("===================")