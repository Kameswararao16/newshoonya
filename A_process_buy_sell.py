from datetime import datetime, timedelta
import pandas as pd
import os
import json
import yaml
import logging
import redis
import time
import sendtelegram as tg

# ===========================================================
# Input NIFTY stocks
# ==========================================================
DATA_FOLDER = "nifty100_data_today"
NIFTY = pd.read_csv("NIFTY50_Tokens.csv")
NIFTY = NIFTY.to_dict("records")

#====================================================================
# Detect candlestick patterns
def detect_candlestick_pattern(candles, stkname, dh, dl, dhw, dlw, hX, lX, hwX, lwX, minmovement):

    if len(candles) < 2:
        print("Not enough candles to detect patterns")
        return None

    print(f"Detecting patterns for {len(candles)} candles")
    print(candles)
    prev = candles.iloc[-2]
    curr = candles.iloc[-1]
    print(f"Previous candle: {prev}")
    print(f"Current candle: {curr}")
    # Previous candle
    po = float(prev["Open"])
    ph = float(prev["High"])
    pl = float(prev["Low"])
    pc = float(prev["Close"])
    print(f"Previous candle - Open: {po}, High: {ph}, Low: {pl}, Close: {pc}")
    # Current candle
    co = float(curr["Open"])
    ch = float(curr["High"])
    cl = float(curr["Low"])
    cc = float(curr["Close"])
    print(f"Current candle - Open: {co}, High: {ch}, Low: {cl}, Close: {cc}")
    # -------------------------
    # Previous candle properties
    # -------------------------
    p_body = abs(pc - po)
    p_upper = ph - max(po, pc)
    p_lower = min(po, pc) - pl
    p_range = ph - pl

    # Current candle properties
    c_body = abs(cc - co)
    c_upper = ch - max(co, cc)
    c_lower = min(co, cc) - cl
    c_range = ch - cl

    # Body should be at least 60% of the entire candle
    pstrong_body = p_body >= 0.4 * p_range
    cstrong_body = c_body >= 0.4 * c_range

    # Add check last candle is either at high or low
    buffer = 0.25 * c_range
    print(f"Buffer: {buffer}")

    last_candle_at_dhigh = abs(max(cc, co) - dh) <= buffer
    last_candle_at_dlow = abs(min(cc, co) - dl) <= buffer
    last_candle_at_dhigh_wick = abs(max(ch, cl) - dhw) <= buffer
    last_candle_at_dlow_wick = abs(min(ch, cl) - dlw) <= buffer

    last_candle_at_highX = abs(max(cc, co) - hX) <= buffer
    last_candle_at_lowX = abs(min(cc, co) - lX) <= buffer
    last_candle_at_highX_wick = abs(max(ch, cl) - hwX) <= buffer
    last_candle_at_lowX_wick = abs(min(ch, cl) - lwX) <= buffer

    if (last_candle_at_dhigh or last_candle_at_dhigh_wick):
        print("Last candle is at day high.")
        if abs(dhw-dlw) < minmovement:
            print("Not enough bullish momentum, skipping pattern detection.")
            return None
    elif (last_candle_at_dlow or last_candle_at_dlow_wick):
        print("Last candle is at day low.")
        if abs(dhw-dlw) < minmovement:
            print("Not enough bearish momentum, skipping pattern detection.")
            return None
    elif (last_candle_at_highX or last_candle_at_highX_wick):
        print("Last candle is at X-candle high.")
        if abs(hwX-lwX) < minmovement:
            print("Not enough bullish momentum, skipping pattern detection.")
            return None
    elif (last_candle_at_lowX or last_candle_at_lowX_wick):
        print("Last candle is at X-candle low.")
        if abs(hwX-lwX) < minmovement:
            print("Not enough bearish momentum, skipping pattern detection.")
            return None

    else:
        print("Last candle is neither day high/low nor last X-candle high/low")
        return None

    now = curr["Date"]
    entry = round((ch + cl) / 2, 2)
    # ==================================================
    # Bullish Engulfing
    # ==================================================
    print(f"pc: {pc}, po: {po}, cc: {cc}, co: {co}, cstrong_body: {cstrong_body}, pstrong_body: {pstrong_body}")
    if (pc <= po and
        cc >= co and
        co <= pc and
        cc >= po and
        cstrong_body and
        pstrong_body and
        (last_candle_at_lowX or last_candle_at_dlow)):
        print("BUY:Bullish Engulfing detected")

        tg.send_telegram_alert(
            symbol=stkname,
            signal="BUY",
            entry_price=str(entry),
            stop_loss=str(cl - (c_range*0.1)) ,
            target_price="T1:" + str(hX),
            logic=f"Bullish Engulfing",
            buy_type="Intraday",
            entry_time=str(now)
        )
        # return "Bullish Engulfing"

    # ==================================================
    # Bearish Engulfing
    # ==================================================
    if (pc >= po and
        cc <= co and
        co >= pc and
        cc <= po and
        cstrong_body and
        pstrong_body and 
        (last_candle_at_highX or last_candle_at_dhigh)):
        print("SELL:Bearish Engulfing detected")
        tg.send_telegram_alert(
            symbol=stkname,
            signal="SELL",
            entry_price=str(entry),
            stop_loss=str(ch + (c_range*0.1)),
            target_price="T1:" + str(lX),
            logic=f"Bearish Engulfing",
            buy_type="Intraday",
            entry_time=str(now)
        )
        # return "Bearish Engulfing"

    # ==================================================
    # Hammer + Confirmation
    # ==================================================
    hammer = (
        # p_lower >= p_body * 2 and
        # p_upper <= p_body * 0.3 and
        (c_lower >= 0.50 * c_range and c_body >= 0.1 * c_range)
        or
        (c_lower >= 0.70 * c_range)  # Ensure the body is not too small
    )
    print(f"c_lower: {c_lower}, 0.5*c_range: {0.5*c_range}, 0.7*c_range: {0.7*c_range}, c_body: {c_body}, 0.1*c_range: {0.1*c_range}")
    bullish_confirmation = True  # Placeholder for actual confirmation logic
    # bullish_confirmation = (
    #     cc > co and                    # Green candle
    #     c_body > p_body and            # Strong body
    #     cc > ph                        # Closes above Hammer high
    # )

    if hammer and bullish_confirmation and (last_candle_at_lowX or last_candle_at_dlow):
        print("BUY: Hammer + Confirmation detected")
        tg.send_telegram_alert(
            symbol=stkname,
            signal="BUY",
            entry_price=str(entry),
            stop_loss=str(cl - (c_range*0.1)),
            target_price="T1:" + str(hX),
            logic=f"Hammer",
            buy_type="Intraday",
            entry_time=str(now)
        )
        # return "Hammer Confirmation"

    # ==================================================
    # Shooting Star + Confirmation
    # ==================================================
    shooting_star = (
        # c_upper >= c_body * 2 and
        # c_lower <= c_body * 0.3 and
        (c_upper >= 0.50 * c_range and c_body >= 0.1 * c_range)
        or
        (c_upper >= 0.70 * c_range)
    )
    print(f"c_upper: {c_upper}, 0.5*c_range: {0.5*c_range}, 0.7*c_range: {0.7*c_range}, c_body: {c_body}, 0.1*c_range: {0.1*c_range}")
    bearish_confirmation= True  # Placeholder for actual confirmation logic
    # bearish_confirmation = (
    #     cc < co and                    # Red candle
    #     c_body > p_body and            # Strong body
    #     cc < pl                        # Closes below Shooting Star low
    # )

    if shooting_star and bearish_confirmation and (last_candle_at_highX or last_candle_at_dhigh):
        print("SELL: Shooting Star + Confirmation detected")
        tg.send_telegram_alert(
            symbol=stkname,
            signal="SELL",
            entry_price=str(entry),
            stop_loss=str(ch + (c_range*0.1)),
            target_price="T1: " + str(lX),
            logic=f"Shooting Star",
            buy_type="Intraday",
            entry_time=str(now)
        )
        # return "Shooting Star Confirmation"

    return None    

# =========================================================
# Process all stocks and detect patterns
# =========================================================
def process_buy_sell(api):
    print("Starting to process all stocks for buy/sell signals...")
    # time.sleep(5)  # Wait for 5 seconds before starting
    for stock in NIFTY:
        try:
            file = os.path.join( DATA_FOLDER, stock["Symbol"]+".csv")
            if not os.path.exists(file):
                print(stock["Symbol"], "missing data")
                continue

            df = pd.read_csv(file)
            df["Date"] = pd.to_datetime(df["Date"])
            dh = (df[["Open","Close"]]).max().max()
            dl = (df[["Open","Close"]]).min().min()
            dhw = df["High"].max()
            dlw = df["Low"].min()
            hX = df.iloc[-12:-1][["Open", "Close"]].max().max()
            lX = df.iloc[-12:-1][["Open", "Close"]].min().min()
            hwX = df.iloc[-12:-1]["High"].max()
            lwX = df.iloc[-12:-1]["Low"].min()
            print(f"Processing stock: {stock['Symbol']}, High: {dh}, Low: {dl}, High Wick: {dhw}, Low Wick: {dlw}")
            print(f"11-candle High: {hX}, 11-candle Low: {lX}, 11-candle High Wick: {hwX}, 11-candle Low Wick: {lwX}")
            df = (df.sort_values("Date").tail(3))

            # #====test=====
            # df = df.sort_values("Date")
            # print(f"df: {len(df)}")

            # for i in range(len(df) - 1):
            #     window = df.iloc[i:i+2]
            #     dh = (df.iloc[0:i+2][["Open","Close"]]).max().max()
            #     dl = (df.iloc[0:i+2][["Open","Close"]]).min().min()
            #     dhw = df.iloc[0:i+2]["High"].max()
            #     dlw = df.iloc[0:i+2]["Low"].min()
            #     print(f"Window index {i}: High: {dh}, Low: {dl}, High wick: {dhw}, Low wick: {dlw}")
            #     print(f"Processing stock: {stock['Symbol']}")
            #     detect_candlestick_pattern(window, stock['Symbol'], dh, dl, dhw, dlw, hX, lX, hwX, lwX)
            #     # print(f"waiting 10 second before next stock...")
            #     # time.sleep(10)
            # #=============

            if len(df)<3: 
                print(f"Not enough data to process {stock['Symbol']}")
                continue

            # print(f"Processing stock: {stock['Symbol']}")
            detect_candlestick_pattern(df, stock['Symbol'], dh, dl, dhw, dlw, hX, lX, hwX, lwX, round(float(stock['LotSize']) * 0.4))
        except Exception as e:
            print(stock["Symbol"], e)

    # print("DOWNLOAD COMPLETE")
#===================TEST===================================
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
# process_buy_sell(api)