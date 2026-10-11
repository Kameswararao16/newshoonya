from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import os
import json
import yaml
import logging
import redis
import time
from pathlib import Path
import sendtelegram as tg

# ===========================================================
# Input NIFTY stocks
# ===========================================================
DATA_FOLDER = "nifty100_data_today"
NIFTY = pd.read_csv("NIFTY50_Tokens.csv")
NIFTY = NIFTY.to_dict("records")
# ===========================================================
# Read previous day data from history
folder = Path("nifty100_data")
previous_day_data = {}

for file in folder.glob("*.csv"):
    try:
        df = pd.read_csv(file)
        if df.empty: 
            continue

        # Make sure data is sorted by Date
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.dropna(subset=["Date"]).sort_values("Date")
        if df.empty:
            continue

        # Get latest candle
        latest = df.iloc[-1]

        # Stock name from filename
        stock_name = file.stem
        high = float(np.asarray(latest["High"]).item())
        low = float(np.asarray(latest["Low"]).item())
        # 25% of high-low range of yesterdays candle
        p25 =round((high - low) * 0.25, 2)
        p05 = round((high - low) * 0.05, 2)
        print(f"Stock: {stock_name}, Latest candle: {latest}, 25% of range: {p25}, High: {high}, Low: {low}, 5% of range: {p05}")
        # Fill per stock data in dictionary
        previous_day_data[stock_name] = {
            "High+100"  : round(high + (4 * p25), 2),
            "High+75"   : round(high + (3 * p25), 2),
            "High+50"   : round(high + (2 * p25), 2),
            "High+25"   : round(high + (1* p25), 2),
            "High"      : round(high, 2),
            "High-25"   : round(high - (1 * p25), 2),
            "Mid"       : round(low + (2* p25), 2),
            "Low+25"    : round(low + (1 * p25), 2),
            "Low"       : round(low, 2),
            "Low-25"    : round(low - (1 * p25), 2),
            "Low-50"    : round(low - (2 * p25), 2),
            "Low-75"    : round(low - (3 * p25), 2),
            "Low-100"   : round(low - (4 * p25), 2),           
            "5%_of_range": p05,
            "25%_of_range": p25
        }
        print(f"previous_day_data[{stock_name}]: {previous_day_data[stock_name]}")

    except Exception as e:
        print(f"Error reading {file}: {e}")

# print(previous_day_data)
# ===========================================================
# redis
redisObject = redis.Redis(host='localhost', port=6379, db=0)
key = "HTA:Buy"
#====================================================================
# Detect candlestick patterns
def detect_candlestick_pattern(last_5_candles, stkname, day_high, day_low):

    c_candle = last_5_candles.iloc[-1]
    c_cc = float(c_candle["Close"])
    c_co = float(c_candle["Open"])
    c_color = "GREEN" if c_cc > c_co else "RED"
    c_body = round(abs(c_cc - c_co), 2)
    c_range = round(c_candle["High"] - c_candle["Low"], 2)
    c_upper_wick = round(c_candle["High"] - max(c_candle["Open"], c_candle["Close"]), 2)
    c_lower_wick = round(min(c_candle["Open"], c_candle["Close"]) - c_candle["Low"], 2)
    print(f"Current candle: {c_candle}, Color: {c_color}, Upper Wick: {c_upper_wick}, Lower Wick: {c_lower_wick}, Body: {c_body}, Range: {c_range}")
    #------------------------Pattern Indentification---------------------
    # Marubozu
    marubozu = (c_body >= 0.89 * c_range)
    print(f"marubozu: {marubozu}")
    # Shooting Star - Bearish
    shooting_star = (
        (c_upper_wick > 0.40 * c_range and c_lower_wick < 0.40 * c_range)
    )
    print(f"shooting_star: {shooting_star}")
    # Hammer- Bullish
    hammer = (
        (c_lower_wick > 0.40 * c_range and c_upper_wick < 0.40 * c_range)
    )
    print(f"hammer: {hammer}")
    #------------------------Find nearest and notify---------------------
    # Get levels and tolerance
    levels = previous_day_data[stkname]
    tolerance = levels["5%_of_range"]
    print(f"Tolerance for {stkname}: {tolerance}")
    print(f"levels for {stkname}: {levels}")
    # Find nearest level within tolerance
    matches = {
        name: price
        for name, price in levels.items()
        if name != "5%_of_range"
        and abs(price - c_cc) <= tolerance
    }

    # Get nearest level
    if matches:
        nearest = min(matches, key=lambda x: abs(matches[x] - c_cc))
        print(stkname, nearest, matches[nearest])
        # Open & close above nearest level # with 25% of range
        if(c_cc > matches[nearest] and c_co > matches[nearest]): # and (abs(c_candle["High"] - 0.15 *c_range) > matches[nearest])):
            print(f"Current candle closed above the nearest level.")
            # Check if current candle is green
            if (c_color == "GREEN" and (marubozu or hammer)):
                print(f"Current candle is GREEN.")  
                sig = "BUY"
                if(abs(day_low - matches[nearest]) < tolerance): 
                    sig = "STRONG BUY"
                tg.send_telegram_alert(symbol=stkname,
                                        signal=sig,
                                        entry_price=str(matches[nearest]),
                                        stop_loss=str(matches[nearest] - tolerance),
                                        target_price="T1: " + str(matches[nearest] + previous_day_data[stkname]["25%_of_range"]) + " T2: " + str(matches[nearest] + 2*previous_day_data[stkname]["25%_of_range"]),
                                        logic=f"Yesterday's Candle",
                                        buy_type="Intraday",
                                        entry_time=str(c_candle["Date"])
                                        )     
        # open & close below nearest level # with 25% of range          
        elif(c_cc < matches[nearest] and c_co < matches[nearest]): #and (abs(c_candle["Low"] + 0.15 *c_range) < matches[nearest])):
            print(f"Current candle closed below the nearest level.")
            # Check if current candle is red
            if (c_color == "RED" and (marubozu or shooting_star)):
                print(f"Current candle is RED.")
                # Indicate strong sell when it is day's high
                sig = "SELL"
                if(abs (day_high - matches[nearest]) < tolerance): 
                    sig = "STRONG SELL"
                tg.send_telegram_alert(symbol=stkname,
                                        signal=sig,
                                        entry_price=str(matches[nearest]),
                                        stop_loss=str(matches[nearest] + tolerance),
                                        target_price="T1: " + str(matches[nearest] - previous_day_data[stkname]["25%_of_range"]) + " T2: " + str(matches[nearest] - 2*previous_day_data[stkname]["25%_of_range"]),
                                        logic=f"Yesterday's Candle",
                                        buy_type="Intraday",
                                        entry_time=str(c_candle["Date"])
                                        )
    else:
        print(stkname, "No nearby level")


    # if(stkname == "NIFTY50" and signal_type != None):
    #     # Store in redis
    #     signal_data = {
    #             "symbol": stkname,
    #             "signal": signal_type,
    #             "entry_price": str(entry),
    #             "stop_loss": str(stop_loss),
    #             "target_price": str(target),
    #             "entry_time": str(now)
    #         }
    #     redisObject.set(key, json.dumps(signal_data))
    #     # Test
    #     buyData = json.loads(redisObject.get(key))
    #     print(f"buyData: {buyData}")
    return None
    

# =========================================================
# Process all stocks and detect patterns
# =========================================================
def process_buy_sell():
    print("Starting to process all stocks for buy/sell signals...")
    # time.sleep(5)  # Wait for 5 seconds before starting
    for stock in NIFTY:
        print(f"Processing stock: {stock['Symbol']}")
        lsize = float(stock['LotSize'])
        try:
            file = os.path.join( DATA_FOLDER, str(stock["Token"])+".csv")
            if not os.path.exists(file):
                print(stock["Symbol"], "missing data")
                continue

            df = pd.read_csv(file)
            df["Date"] = pd.to_datetime(df["Date"], dayfirst=True)
            df = df.sort_values("Date")
            # # wait for first 1 candles
            # if len(df)<1: 
            #     print(f"Not enough data to process {stock['Symbol']}")
            #     continue

            # d_high = df.iloc[:-1]["High"].max()
            # d_low = df.iloc[:-1]["Low"].min()
            # last_5_candles = df.tail(5)
            # print(f"last_5_candles: {last_5_candles}") 

            #====test=====
            print(f"df: {len(df)}")
            for i in range(len(df)):
                last_5_candles = df.iloc[max(0, i-4):i+1]
                d_high = df.iloc[0:i]["High"].max()
                d_low = df.iloc[0:i]["Low"].min()
                print(f"last_5_candles: {last_5_candles}") 
                detect_candlestick_pattern(last_5_candles, stock['Symbol'], d_high, d_low)
                # print(f"waiting 10 second before next stock...")
                # time.sleep(10)
            #=============

            # print(f"Processing stock: {stock['Symbol']}")
            # detect_candlestick_pattern(last_5_candles, stock['Symbol'], d_high, d_low)

        except Exception as e:
            print(stock["Symbol"], e)

    # print("DOWNLOAD COMPLETE")
# #===================TEST===================================
process_buy_sell()