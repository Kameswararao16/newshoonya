# process_data.py

import pandas as pd
import numpy as np
import os
import sendtelegram as tg

# =====================================================
# SETTINGS
# =====================================================

DATA_FOLDER = "nifty100_data"

n100 = pd.read_csv("NIFTY100_Tokens_org.csv")
NIFTY100 = n100.to_dict("records")

pd.set_option("display.max_columns", None)
pd.set_option("display.width", None)

# # =====================================================
# # WICK LOGIC
# # =====================================================

# def add_wick_signal(df):

#     total_range = df["High"] - df["Low"]

#     upper_wick = (
#         df["High"]
#         - df[["Open","Close"]]
#         .max(axis=1)
#     )

#     lower_wick = (
#         df[["Open","Close"]]
#         .min(axis=1)
#         - df["Low"]
#     )

#     upper_pct = upper_wick / total_range
#     lower_pct = lower_wick / total_range

#     prev_high = df["High"].shift(1)
#     prev_low = df["Low"].shift(1)

#     green = df["Close"] > df["Open"]
#     red = df["Close"] < df["Open"]

#     df["WickSignal"] = np.select(
#         [
#             (df["Low"] < prev_low) &
#             (
#                 (lower_pct > 0.70) |
#                 ((lower_pct > 0.40) & (upper_pct < 0.10))
#             ),

#             (df["High"] > prev_high) &
#             (
#                 (upper_pct > 0.70) |
#                 ((upper_pct > 0.40) & (lower_pct < 0.10))
#             ),
#         ],
#         [
#             "Bullish",
#             "Bearish",
#         ],
#         default="Neutral",
#     )

#     return df

# # =====================================================
# # ENGULFING
# # =====================================================

# def engulf_wick_reference(df):

#     result = []

#     for i in range(len(df)):

#         if i == 0:
#             result.append("Neutral")
#             continue

#         prev = df.iloc[i-1]
#         cur = df.iloc[i]

#         bullish = (
#             cur.Close > cur.Open
#             and
#             cur.Open < min(prev.Open,prev.Close)
#             and
#             cur.Close > max(prev.Open,prev.Close)
#         )

#         bearish = (
#             cur.Close < cur.Open
#             and
#             cur.Open > max(prev.Open,prev.Close)
#             and
#             cur.Close < min(prev.Open,prev.Close)
#         )

#         if bullish:
#             result.append("Bullish")

#         elif bearish:
#             result.append("Bearish")

#         else:
#             result.append("Neutral")

#     return pd.Series(
#         result,
#         index=df.index
#     )

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


# # =====================================================
# # BULLISH TWEEZER BOTTOM
# # =====================================================

# def tweezers(df):

#     result = []

#     for i in range(len(df)):

#         if i == 0:
#             result.append("Neutral")
#             continue

#         prev = df.iloc[i-1]
#         cur = df.iloc[i]

#         same_low = (
#             abs(prev.Low - cur.Low)
#             <= (cur.Close * 0.001)
#         )
#         prev_red = prev.Close < prev.Open
#         cur_green = cur.Close > cur.Open

#         same_high = (
#             abs(prev.High-cur.High)
#             <= (cur.Close*0.001)
#         )
#         prev_green = prev.Close > prev.Open
#         cur_red = cur.Close < cur.Open

#         if same_low and prev_red and cur_green:
#             result.append("Bullish")
#         elif same_high and prev_green and cur_red:
#             result.append("Bearish")
#         else:
#             result.append("Neutral")

#     return pd.Series(
#         result,
#         index=df.index
#     )

# =====================================================
# FINAL SIGNAL
# =====================================================

def generate_signals(df):

    df["FinalSignal"]="Neutral"
    df["TriggerLogic"]=""

    for i in range(len(df)):
        wick = df["WickSignal"].iloc[i]
        engulf = df["EngulfType"].iloc[i]
        tweezer = df["Tweezer"].iloc[i]


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


# # =====================================================
# # Find last swing group
# # =====================================================
# def body_high(c):
#     return max(c['Open'], c['Close'])

# def body_low(c):
#     return min(c['Open'], c['Close'])


# def last_group(df):
#     """
#     df columns:
#     open, high, low, close
#     oldest -> newest
#     """
#     # print("start last_group....")
#     n = len(df)
#     # print(f"n: {n}")
#     if n == 0:
#         print(f"None.")
#         return None

#     # Start from latest candle
#     idx = n - 1

#     grp_start = idx

#     comb_body_high = body_high(df.iloc[idx])
#     comb_body_low = body_low(df.iloc[idx])
#     # print(f"{comb_body_high}, {comb_body_low}")
#     while idx > 0:

#         prev = df.iloc[idx - 1]

#         prev_high = prev["High"]
#         prev_low = prev["Low"]
#         # print(f"{prev_low}, {prev_high}")
#         # Break previous candle?
#         if comb_body_high > prev_high or comb_body_low < prev_low:
#             break

#         # Merge candle
#         comb_body_high = max(comb_body_high, body_high(prev))
#         comb_body_low = min(comb_body_low, body_low(prev))

#         grp_start = idx - 1
#         idx -= 1

#     group = df.iloc[grp_start:]
#     # print(f"group: {group}")
#     return {
#         "start": grp_start,
#         "end": n - 1,
#         "high": group["High"].max(),
#         "low": group["Low"].min(),
#         "candles": group
#     }

# =====================================================
# PROCESS ALL STOCKS
# =====================================================


# print("\nSTART SCAN\n")
print("Symbol, Date, Type of entry, Price Movement, Logic, Entry, SL, Target, Current Price Position, High Profit")

# Read today's data 
today_ohlc = (
    pd.read_csv("Today_OHLC.csv")
      .set_index("Symbol")
      .to_dict("index")
)
# print(today_ohlc)

#Read historical data and process each stock
for stock in NIFTY100:

    ticker = stock["Symbol"]

    try:

        file = os.path.join(DATA_FOLDER, ticker+".csv")
        if not os.path.exists(file):
            print(ticker, "missing data")
            continue

        df = pd.read_csv(file)
        df["Date"] = pd.to_datetime(df["Date"])
        df = (df.sort_values("Date").tail(60))

        #--------------------------------------
        # Add today's OHLC if available
        if ticker in today_ohlc:

            print(f"Adding today's OHLC for {ticker}")
            new_row = pd.DataFrame([{
                "Date": pd.to_datetime(today_ohlc[ticker]["Date"]),
                "Open": today_ohlc[ticker]["Open"],
                "High": today_ohlc[ticker]["High"],
                "Low": today_ohlc[ticker]["Low"],
                "Close": today_ohlc[ticker]["Close"],
                "Volume": np.nan      # or 0 if you prefer
            }])
            print(new_row)

            df = (
                pd.concat([df, new_row], ignore_index=True)
                .drop_duplicates(subset="Date", keep="last")
                .sort_values("Date")
                .tail(60)
            )
            print(f"df: {df.iloc[-1]}")
        #----------------------------------------

        if len(df)<20: 
            continue

        # Get trned and range position
        df = add_14day_trend(df)
        df = add_14day_range_position(df)
        #-----------------------------------------------------------------------
        # Simple last candle logic
        last_candle_data = df.iloc[-1]
        lRange = last_candle_data["High"] - last_candle_data["Low"]
        lbody = abs(last_candle_data["Close"] - last_candle_data["Open"])
        lMid = (last_candle_data["High"] + last_candle_data["Low"])/2
        uWick = last_candle_data["High"] - max(last_candle_data["Open"], last_candle_data["Close"])
        lWick = min(last_candle_data["Open"], last_candle_data["Close"]) - last_candle_data["Low"]
        uWickPct = uWick / lRange
        lWickPct = lWick / lRange
        bPct = lbody / lRange
        #-----------------Logic-1----------------------
        # print(f"ticker: {ticker}, uWickPct: {uWickPct}, lWickPct: {lWickPct}, lRange: {lRange}, bPct: {bPct}")
        # Last candle is green + No pull back by sellers or long pull back buyers or not Doji
        if ((last_candle_data["Close"] > last_candle_data["Open"]) and 
            ( (lWickPct <= 0.1) or (lWickPct >= 0.7) or ((lWickPct >= 0.49) and (bPct >= 0.3)) )):
            # print("Green")
            if last_candle_data["Trend"] == "Downtrend":
                # print("Green-Downtrend")
                if last_candle_data["RangePct"] <= 0.3:
                    # print("Grean-Near 14 days low.")
                    print(ticker,",", last_candle_data.Date.date(), ", DAY, Bullish, Last Candle,", 
                            last_candle_data["Close"], ",", last_candle_data["Open"], ",", 
                            round(last_candle_data["Close"]+lRange, 2))
                    # Send telegram alert
                    tg.send_telegram_alert(symbol=ticker,
                                        signal="BUY",
                                        entry_price=str(round(last_candle_data["Close"], 2)),
                                        stop_loss=str(round(last_candle_data["Open"], 2)),
                                        target_price="T1: " + str(round(last_candle_data["Close"]+lRange, 2)) ,
                                        logic=f"Yesterday's Candle",
                                        buy_type="Intraday",
                                        entry_time="Any Time")
        # Last candle is red + No pull back by buyers or long pull back seller or not Doji
        elif ((last_candle_data["Close"] < last_candle_data["Open"]) and 
              ( (uWickPct >= 0.7) or (uWickPct <= 0.1) or ((uWickPct >= 0.49) and (bPct >= 0.3)) )):
            # print("Red")
            if last_candle_data["Trend"] == "Uptrend":
                # print("Red-Uptrend")
                if last_candle_data["RangePct"] >= 0.7:
                    # print("Red-Near 14 days high.")
                    print(ticker,",", last_candle_data.Date.date(), ", DAY, Bearish, Last Candle,", 
                            last_candle_data["Close"], ",", last_candle_data["Open"], ",", 
                            round(last_candle_data["Close"]-lRange, 2))
                    # Send telegram alert
                    tg.send_telegram_alert(symbol=ticker,
                                        signal="SELL",
                                        entry_price=str(round(last_candle_data["Close"], 2)),
                                        stop_loss=str(round(last_candle_data["Open"], 2)),
                                        target_price="T1: " + str(round(last_candle_data["Close"]-lRange, 2)) ,
                                        logic=f"Yesterday's Candle",
                                        buy_type="Intraday",
                                        entry_time="Any Time")
        #---------------Logic-2----------------------------
        # Previous-previous day
        prev2 = df.iloc[-2]  
        prev2_high = float(prev2["High"])
        prev2_low = float(prev2["Low"])
        # Previous day
        prev = df.iloc[-1]    
        prev_high = float(prev["High"])
        prev_low = float(prev["Low"])
        prev_close = float(prev["Close"])
        prev_range = prev_high - prev_low
        #Signal
        signal = "NO SIGNAL"
        if prev_close > prev2_high: signal = "BUY"
        elif prev_close < prev2_low:  signal = "SELL"
        # EntrY levels
        entry_high_20 = round(prev_high - (prev_range * 0.20), 2)
        entry_high_45 = round(prev_high - (prev_range * 0.45), 2)
        entry_low_20 = round(prev_low + (prev_range * 0.20), 2)
        entry_low_45 = round(prev_low + (prev_range * 0.45), 2)
        # Exit levels
        exit_high_30 = round(prev_high - (prev_range * 0.30), 2)
        exit_high_55 = round(prev_high - (prev_range * 0.55), 2)
        exit_low_30 = round(prev_low + (prev_range * 0.30), 2)
        exit_low_55 = round(prev_low + (prev_range * 0.55), 2)
        # Target levels
        target_high_20 = round(entry_high_20 + (prev_range * 0.50), 2)
        target_high_45 = round(entry_high_45 + (prev_range * 0.50), 2)
        target_low_20 = round(entry_low_20 - (prev_range * 0.50), 2)
        target_low_45 = round(entry_low_45 - (prev_range * 0.50), 2)
        # Send Signal
        if signal == "BUY":
            # Send telegram alert
            tg.send_telegram_alert(symbol=ticker,
                                signal="BUY",
                                entry_price="E1:" + str(entry_high_20) + ", E2:" + str(entry_high_45) ,
                                stop_loss="SL1:" + str(exit_high_30) + ", SL2:" + str(exit_high_55) ,
                                target_price="T1:" + str(target_high_20) + ", T2:" + str(target_high_45) ,
                                logic=f"Yesterday's Candle breakout",
                                buy_type="Intraday",
                                entry_time="Any Time")

        elif signal == "SELL":
            # Send telegram alert
            tg.send_telegram_alert(symbol=ticker,
                                signal="SELL",
                                entry_price="E1:" + str(entry_low_20) + ", E2:" + str(entry_low_45) ,
                                stop_loss="SL1:" + str(exit_low_30) + ", SL2:" + str(exit_low_55) ,
                                target_price="T1:" + str(target_low_20) + ", T2:" + str(target_low_45) ,
                                logic=f"Yesterday's Candle",
                                buy_type="Intraday",
                                entry_time="Any Time")

        continue
        # #---------------------------------------------------------------------
        # # Not usefull at present, but can be used in future for more complex logic

        # df["Wick"] = add_wick_signal(df)
        # df["EngulfType"] = engulf_wick_reference(df)
        # df["Tweezer"] = tweezers(df)
        # df = generate_signals(df)

        # last = df.iloc[-1]
        # if last["FinalSignal"]=="Neutral":
        #     continue

        # # entry = round(float(last.Close), 2)
        # lastSwingGroupData = last_group(df)
        # # print(lastSwingGroupData)
        # entry = round(float((df["Low"].iloc[-1] + df["High"].iloc[-1])/2), 2)
        # if last.FinalSignal=="Bullish":
        #     # sl = round(float(last.Low), 2)
        #     # target = round(entry + (entry-sl)*2, 2)
        #     sl = lastSwingGroupData["low"]
        #     target = lastSwingGroupData["high"]
        #     watch = (abs(entry -sl)*1.5 < abs(entry -target))
        #     # if(df["WickSignal"].iloc[i]):
        #     # elif(df["EngulfType"].iloc[i])
        #     side="DAY"
        # else:
        #     # sl = round(float(last.High), 2)
        #     # target = round( entry - (sl-entry)*2, 2)
        #     sl = lastSwingGroupData["high"]
        #     target = lastSwingGroupData["low"]
        #     watch = (abs(entry -sl)*1.5 < abs(entry -target))
        #     side="DAY"

        # print(ticker,",", last.Date.date(), ",", side, ",", 
        #         last.FinalSignal, ",", last.TriggerLogic, ",", 
        #         entry, ",", sl, ",", target, ",", last.RangeZone,",", watch
        # )

    except Exception as e:
        print(ticker, e)


# print("\n===================")
# print("SCAN COMPLETED")
# print("===================")