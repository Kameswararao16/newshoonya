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
# ===========================================================
DATA_FOLDER = "nifty100_data_today"
NIFTY = pd.read_csv("NIFTY50_Tokens.csv")
NIFTY = NIFTY.to_dict("records")

#====================================================================
# Detect candlestick patterns
def detect_candlestick_pattern(first_3_candles, candles, stkname, lsize, dh, dl, dhw, dlw, hX, lX, hwX, lwX, minmovement):

    if len(candles) < 2:
        print("Not enough candles to detect patterns")
        return None

    print(f"first_3_candles: {first_3_candles}")
    f_dhw = first_3_candles["High"].max()
    f_dlw = first_3_candles["Low"].min()
    f_dh = first_3_candles[["Open", "Close"]].max().max()
    f_dl = first_3_candles[["Open", "Close"]].min().min()
    f_midw = round((f_dhw + f_dlw) / 2, 2)
    f_mid = round((f_dh + f_dl) / 2, 2)
    print(f"First candle - f_dh: {f_dh}, f_dl: {f_dl}, f_dhw: {f_dhw}, f_dlw: {f_dlw},  f_midw: {f_mid}")
    print(f"Day - dh: {dh}, dl: {dl}, dhw: {dhw}, dlw: {dlw}")
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
    p_body = round(abs(pc - po), 2)
    p_upper_wick = round(ph - max(po, pc), 2)
    p_lower_wick = round(min(po, pc) - pl, 2)
    p_range = round(ph - pl, 2)
    print(f"p_body: {p_body}, p_upper_wick: {p_upper_wick}, p_lower_wick: {p_lower_wick}, p_range: {p_range}")

    # Current candle properties
    c_high = max(cc, co)
    c_low = min(cc, co)
    c_body = round(abs(cc - co), 2)
    c_upper_wick = round(ch - max(co, cc), 2)
    c_lower_wick = round(min(co, cc) - cl, 2)
    c_range = round(ch - cl, 2)
    print(f"c_high: {c_high}, c_low: {c_low}, c_body: {c_body}, c_upper_wick: {c_upper_wick}, c_lower_wick:  {c_lower_wick}, c_range: {c_range}")

    # Body should be at least 60% of the entire candle
    # pstrong_body = p_body >= 0.4 * p_range
    cstrong_body = c_body >= 0.5 * c_range

    # Add check last candle is either at high or low
    buffer = round(0.20 * lsize, 2)
    print(f"Buffer: {buffer}")

    last_candle_at_fhigh = abs(max(cc, co) - f_dh) <= buffer
    last_candle_at_flow = abs(min(cc, co) - f_dl) <= buffer
    last_candle_at_fhigh_wick = abs(max(ch, cl) - f_dh) <= buffer
    last_candle_at_flow_wick = abs(min(ch, cl) - f_dl) <= buffer
    #--------------First candle logic ----------------------------
    buy_signal = False
    sell_signal = False
    entry = round((ch + cl) / 2, 2)
    target = 0.5 * lsize
    stop_loss = 0.5 * lsize
    now = curr["Date"]
    c_red_candle = (cc < co)
    c_green_candle = (cc > co)
    c_strong_lower_wick = (c_lower_wick > (0.7 * c_body))
    c_strong_upper_wick = (c_upper_wick > (0.7 * c_body))
    c_strong_body = c_body >= 0.4 * c_range
    #------------------------Pattern Indentification---------------------
    # Marubozu
    marubozu = (c_body >= 0.89 * c_range)
    print(f"marubozu: {marubozu}")
    # Shooting Star - Bearish
    shooting_star = (
        (c_upper_wick >= 0.50 * c_range and c_body >= 0.1 * c_range)    # not a doji
        or
        (c_upper_wick > (0.7 * c_range))
    )
    print(f"shooting_star: {shooting_star}")
    # Hammer- Bullish
    hammer = (
        (c_lower_wick >= 0.50 * c_range and c_body >= 0.1 * c_range)    # not a doji
        or
        (c_lower_wick > (0.7 * c_range))
    )
    print(f"hammer: {hammer}")
    # Bullish Engulfing
    bullish_engulf =    (   pc <= po+(0.05*lsize) and
                            cc+(0.05*lsize) >= co and
                            co <= pc+(0.05*lsize) and
                            cc+(0.05*lsize) >= po and
                            cstrong_body 
    )
    print(f"bullish_engulf: {bullish_engulf}")
    # Bearish Engulfing
    bearish_engulf =    (   pc+(0.05*lsize) >= po and
                            cc <= co+(0.05*lsize) and
                            co+(0.05*lsize) >= pc and
                            cc <= po+(0.05*lsize) and
                            cstrong_body 
    )
    print(f"bearish_engulf: {bearish_engulf}")
    # Bullish confirmation
    bullish_confirmation = (
        (marubozu and c_green_candle) or    #   Marubo & Green candle
        bullish_engulf or                   #   Bullish Engulf
        hammer                              #   Hammer
    )
    print(f"bullish_confirmation: {bullish_confirmation}")
    # Bearish conformation 
    bearish_confirmation = (
        (marubozu and c_red_candle) or      #   Marubo & red candle
        bearish_engulf or                   #   Bullish Engulf
        shooting_star                       #   shooting star  
    )
    print(f"bearish_confirmation: {bearish_confirmation}")
    #------------------------Actual Logic----------------------------
    # First candle logic
    # Current candle body is still above first 3-candle high
    if (min(cc, co) > f_dhw): 
        print(f"Price moved beyond first 3-candle high.")
        # Day high is more than first 3-candle high
        if(dhw > f_dhw + (0.5*lsize)):
            print(f"Days high is more to proceed.")
            # Current candle lower wick near 3-candle high (above or below) 
            if( (abs(f_dhw - cl) <= round(0.10 * lsize, 2)) or (f_dhw > cl) ):
                print("Price retraced back to day high.")
                if (bullish_confirmation): # Bullish candle formed
                    print(f"BUY: Bullish confirmation.")
                    buy_signal = True
                    target = entry + round((0.5*lsize), 2)
                    stop_loss = entry - round((0.25*lsize), 2)
                    entry = entry - round(c_range*0.25, 2)
            # Current candle higher wick near day's high
            # Current candle high is still below day's high
            elif( (abs(dhw - ch) <= round(0.10 * lsize, 2)) or ( (dhw < ch) and (max(cc, co) < dhw)) ):
                print("Price is at day high.")
                if(bearish_confirmation): # Bearish candle formed
                    print(f"SELL: Bearish conformation")
                    sell_signal = True
                    target = entry - round((0.5*lsize), 2)
                    stop_loss = entry + round((0.25*lsize), 2)
                    entry = entry + round(c_range*0.25, 2)         
    # Current candle body is still below 3-candle low
    elif(max(cc, co) < f_dlw):  
        print(f"Price moved beyond first 3-candle low.")
        # Day low is below than first 3-candle low
        # Current candle hiher wick near 3-candle low (above or below) 
        if(dlw > f_dlw + (0.5*lsize)): 
            print(f"Days low is more to proceed.")
            if( (abs(f_dlw - ch) < round(0.10 * lsize, 2)) or (f_dlw < ch) ):
                print("Price retraced back to day low.")
                if(bearish_confirmation): # Bearish candle formed
                    print(f"SELL: Bearish conformation")
                    sell_signal = True
                    target = entry - round((0.5*lsize), 2)
                    stop_loss = entry + round((0.25*lsize), 2)
                    entry = entry + round(c_range*0.25, 2)
            # Current candle lower wick near day's low
            # Current candle low is still below day's low
            elif( (abs(dlw - cl) <= round(0.10 * lsize, 2)) or ( (dlw > cl) and (min(cc, co) < dlw)) ):
                print("Price is at day high.")
                if(bearish_confirmation): # Bearish candle formed
                    print(f"BUY: Bullish conformation")
                    buy_signal = True
                    target = entry + round((0.5*lsize), 2)
                    stop_loss = entry - round((0.25*lsize), 2)
                    entry = entry - round(c_range*0.25, 2)
    # Current candle is inside first 3-candles
    elif( (f_dhw > max(cc, co)) and (f_dlw < min(cc, co)) and (abs(f_dhw - f_dlw) > (0.5*lsize)) ):
        print(f"With in first 3-candles.")
        if( (abs(f_dhw - ch) <= round(0.10 * lsize, 2)) or (f_dhw < ch) ):
            print("Price is near first 3-candle high.")
            if(bearish_confirmation): # Bearish candle formed
                print(f"SELL: Bearish conformation")
                sell_signal = True
                target = entry - round((0.5*lsize), 2)
                stop_loss = entry + round((0.25*lsize), 2)
                entry = entry + round(c_range*0.25, 2)
        elif( (abs(f_dlw - cl) < round(0.10 * lsize, 2)) or (f_dlw > cl) ) : 
            print("Price is near first 3-candle low.")   
            if (bullish_confirmation): # Bullish candle formed
                print(f"BUY: Bullish confirmation.")
                buy_signal = True
                target = entry + round((0.5*lsize), 2)
                stop_loss = entry - round((0.25*lsize), 2)
                entry = entry - round(c_range*0.25, 2)
    # Send message
    if(sell_signal == True):
        tg.send_telegram_alert(
            symbol=stkname,
            signal="SELL",
            entry_price=str(entry),
            stop_loss=str(stop_loss),
            target_price="T1: " + str(target) ,
            logic=f"First Candle",
            buy_type="Intraday",
            entry_time=str(now)
        )
    elif(buy_signal == True):
        tg.send_telegram_alert(
            symbol=stkname,
            signal="BUY",
            entry_price=str(entry),
            stop_loss=str(stop_loss),
            target_price="T1: " + str(target),
            logic=f"First Candle",
            buy_type="Intraday",
            entry_time=str(now)
        )
    
    return None
    # #-----------------------------------------------------------------------
    # # if(last_candle_at_fhigh or last_candle_at_fhigh_wick):
    # # elif(last_candle_at_flow or last_candle_at_flow_wick):

    # last_candle_at_dhigh = abs(max(cc, co) - dh) <= buffer
    # last_candle_at_dlow = abs(min(cc, co) - dl) <= buffer
    # last_candle_at_dhigh_wick = abs(max(ch, cl) - dhw) <= buffer
    # last_candle_at_dlow_wick = abs(min(ch, cl) - dlw) <= buffer

    # last_candle_at_highX = abs(max(cc, co) - hX) <= buffer
    # last_candle_at_lowX = abs(min(cc, co) - lX) <= buffer
    # last_candle_at_highX_wick = abs(max(ch, cl) - hwX) <= buffer
    # last_candle_at_lowX_wick = abs(min(ch, cl) - lwX) <= buffer

    # if (last_candle_at_fhigh or last_candle_at_fhigh_wick):
    #     print("Last candle is at first candle high.")
    #     if abs(round(f_dh-f_dl, 2)) < minmovement:
    #         print("Not enough bullish momentum, skipping pattern detection.")
    #         return None
    # elif (last_candle_at_flow or last_candle_at_flow_wick):
    #     print("Last candle is at first candle low.")
    #     if abs(round(f_dh-f_dl, 2)) < minmovement:
    #         print("Not enough bearish momentum, skipping pattern detection.")
    #         return None
    # if (last_candle_at_dhigh or last_candle_at_dhigh_wick):
    #     print("Last candle is at day high.")
    #     if abs(round(dhw-dlw, 2)) < minmovement:
    #         print("Not enough bullish momentum, skipping pattern detection.")
    #         return None
    # elif (last_candle_at_dlow or last_candle_at_dlow_wick):
    #     print("Last candle is at day low.")
    #     if abs(round(dhw-dlw, 2)) < minmovement:
    #         print("Not enough bearish momentum, skipping pattern detection.")
    #         return None
    # elif (last_candle_at_highX or last_candle_at_highX_wick):
    #     print("Last candle is at X-candle high.")
    #     if abs(round(hwX-lwX, 2)) < minmovement:
    #         print("Not enough bullish momentum, skipping pattern detection.")
    #         return None
    # elif (last_candle_at_lowX or last_candle_at_lowX_wick):
    #     print("Last candle is at X-candle low.")
    #     if abs(round(hwX-lwX, 2)) < minmovement:
    #         print("Not enough bearish momentum, skipping pattern detection.")
    #         return None

    # else:
    #     print("Last candle is neither day high/low nor last X-candle high/low")
    #     return None

    
    # entry = round((ch + cl) / 2, 2)
    # # ==================================================
    # # Bullish Engulfing
    # # ==================================================
    # print(f"pc: {pc}, po: {po}, cc: {cc}, co: {co}, cstrong_body: {cstrong_body}, pstrong_body: {pstrong_body}")
    # if (pc <= po and
    #     cc >= co and
    #     co <= pc and
    #     cc >= po and
    #     cstrong_body and
    #     pstrong_body and
    #     (last_candle_at_lowX or last_candle_at_dlow)):
    #     print("BUY:Bullish Engulfing detected")

    #     tg.send_telegram_alert(
    #         symbol=stkname,
    #         signal="BUY",
    #         entry_price=str(entry),
    #         stop_loss=str(round(cl - (c_range*0.1), 2)),
    #         target_price="T1:" + str(hX),
    #         logic=f"Bullish Engulfing",
    #         buy_type="Intraday",
    #         entry_time=str(now)
    #     )
    #     # return "Bullish Engulfing"

    # # ==================================================
    # # Bearish Engulfing
    # # ==================================================
    # if (pc >= po and
    #     cc <= co and
    #     co >= pc and
    #     cc <= po and
    #     cstrong_body and
    #     pstrong_body and 
    #     (last_candle_at_highX or last_candle_at_dhigh)):
    #     print("SELL:Bearish Engulfing detected")
    #     tg.send_telegram_alert(
    #         symbol=stkname,
    #         signal="SELL",
    #         entry_price=str(entry),
    #         stop_loss=str(round(ch + (c_range*0.1), 2)),
    #         target_price="T1:" + str(lX),
    #         logic=f"Bearish Engulfing",
    #         buy_type="Intraday",
    #         entry_time=str(now)
    #     )
    #     # return "Bearish Engulfing"

    # # ==================================================
    # # Hammer + Confirmation
    # # ==================================================
    # hammer = (
    #     (c_lower_wick >= 0.50 * c_range and c_body >= 0.1 * c_range)
    #     or
    #     (c_lower_wick >= 0.70 * c_range)  # Ensure the body is not too small
    # )
    # print(f"c_lower_wick: {c_lower_wick}, 0.5*c_range: {0.5*c_range}, 0.7*c_range: {round(0.7*c_range, 2)}, c_body: {c_body}, 0.1*c_range: {round(0.1*c_range, 2)}")


    # if hammer and bullish_confirmation and (last_candle_at_lowX or last_candle_at_dlow):
    #     print("BUY: Hammer + Confirmation detected")
    #     tg.send_telegram_alert(
    #         symbol=stkname,
    #         signal="BUY",
    #         entry_price=str(entry),
    #         stop_loss=str(round(cl - (c_range*0.1), 2)),
    #         target_price="T1:" + str(hX),
    #         logic=f"Hammer",
    #         buy_type="Intraday",
    #         entry_time=str(now)
    #     )
    #     # return "Hammer Confirmation"

    # # ==================================================
    # # Shooting Star + Confirmation
    # # ==================================================
    # shooting_star = (
    #     (c_upper_wick >= 0.50 * c_range and c_body >= 0.1 * c_range)
    #     or
    #     (c_upper_wick >= 0.70 * c_range)
    # )
    # print(f"c_upper_wick: {c_upper_wick}, 0.5*c_range: {0.5*c_range}, 0.7*c_range: {round(0.7*c_range, 2)}, c_body: {c_body}, 0.1*c_range: {round(0.1*c_range, 2)}")

    # if shooting_star and bearish_confirmation and (last_candle_at_highX or last_candle_at_dhigh):
    #     print("SELL: Shooting Star + Confirmation detected")
    #     tg.send_telegram_alert(
    #         symbol=stkname,
    #         signal="SELL",
    #         entry_price=str(entry),
    #         stop_loss=str(round(ch + (c_range*0.1), 2)),
    #         target_price="T1: " + str(lX),
    #         logic=f"Shooting Star",
    #         buy_type="Intraday",
    #         entry_time=str(now)
    #     )
    #     # return "Shooting Star Confirmation"

    # #=======================================================
    # # Marbozu + Confirmation
    # #=======================================================
    # marubozu = (
    #     (c_upper_wick <= 0.05 * c_range and c_lower_wick <= 0.05 * c_range) and
    #     (c_body >= 0.9 * c_range)
    # )
    # print(f"c_upper_wick: {c_upper_wick}, c_lower_wick: {c_lower_wick}, c_body: {c_body}, c_range: {c_range}, marubozu: {marubozu}")
    # bullish_confirmation = (
    #     cc > co and                    # Green candle
    #     cc > max(pc, po)               # Current closes above previous candle's close or open
    # )
    # if marubozu and bullish_confirmation and (last_candle_at_lowX or last_candle_at_dlow):
    #     print("BUY: Marubozu + Confirmation detected")
    #     tg.send_telegram_alert(
    #         symbol=stkname,
    #         signal="BUY",
    #         entry_price=str(entry),
    #         stop_loss=str(round(cl - (c_range*0.1), 2)),
    #         target_price="T1:" + str(hX),
    #         logic=f"Marubozu",
    #         buy_type="Intraday",
    #         entry_time=str(now)
    #     )
        
    # bearish_confirmation = (
    #     cc < co and                    # Red candle
    #     cc < min(pc, po)               # Closes below previous candle's close or open
    # )   
    # if marubozu and bearish_confirmation and (last_candle_at_highX or last_candle_at_dhigh):
    #     print("SELL: Marubozu + Confirmation detected")
    #     tg.send_telegram_alert(
    #         symbol=stkname,
    #         signal="SELL",
    #         entry_price=str(entry),
    #         stop_loss=str(round(ch + (c_range*0.1), 2)),
    #         target_price="T1: " + str(lX),
    #         logic=f"Marubozu",
    #         buy_type="Intraday",
    #         entry_time=str(now)
    #     )
        
    # return None    

# =========================================================
# Process all stocks and detect patterns
# =========================================================
def process_buy_sell(api):
    print("Starting to process all stocks for buy/sell signals...")
    # time.sleep(5)  # Wait for 5 seconds before starting
    for stock in NIFTY:
        lsize = float(stock['LotSize'])
        try:
            file = os.path.join( DATA_FOLDER, stock["Symbol"]+".csv")
            if not os.path.exists(file):
                print(stock["Symbol"], "missing data")
                continue

            df = pd.read_csv(file)
            df["Date"] = pd.to_datetime(df["Date"])
            df = df.sort_values("Date")
            # wait for first 3 candles
            if len(df)<4: 
                print(f"Not enough data to process {stock['Symbol']}")
                continue
            first_3_candles = df.iloc[:3]

            # #----------------- Get blocks-------------------
            # blocks = []  
            # for i in range(0, len(df) - 1):
            #     # print(f"Processing row {i} of {len(df)}")
            #     row = df.iloc[i]
            #     ch = row["High"]
            #     cl = row["Low"]
            #     if not blocks:
            #         if(round(ch-cl, 2) < (0.8*lsize)):
            #             blocks.extend([cl, ch])
            #         else:
            #             blocks.extend([cl, round((ch+cl)/2, 2)])
            #             blocks.extend([ch])
            #         # print(f"Initial blocks for {stock['Symbol']}: {blocks}")
            #         continue
            #     low = blocks[0]
            #     high = blocks[-1]
            #     if(ch > high):
            #         r = blocks[-1] - blocks[-2]
            #         ext = r * 0.30
            #         # print(f"Current blocks for {stock['Symbol']}: {blocks}, Current candle: High={ch}, Range={r}, Extension={ext}")
            #         if (ch > high+ext):
            #             blocks.extend([ch])
            #     elif(cl < low):
            #         r = blocks[1] - blocks[0]
            #         ext = r * 0.30
            #         # print(f"Current blocks for {stock['Symbol']}: {blocks}, Current candle: Low={cl}, Range={r}, Extension={ext}")
            #         if (cl < low-ext):
            #             blocks.insert(0, cl)
            #     # print(f"Updated blocks for {stock['Symbol']}: {blocks}")
            # print(f"Symbol {stock['Symbol']}: {blocks}")
            # continue  # Skip pattern detection for now, just printing blocks
            #-----------------------------------------------
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
            # print(f"df: {len(df)}")

            # for i in range(len(df) - 1):
            #     window = df.iloc[i:i+2]
            #     df_temp = df.iloc[0:i+1]
            #     dh = (df_temp[["Open","Close"]]).max().max()
            #     dl = (df_temp[["Open","Close"]]).min().min()
            #     dhw = df_temp["High"].max()
            #     dlw = df_temp["Low"].min()
            #     hX = df_temp.iloc[-12:-1][["Open", "Close"]].max().max()
            #     lX = df_temp.iloc[-12:-1][["Open", "Close"]].min().min()
            #     hwX = df_temp.iloc[-12:-1]["High"].max()
            #     lwX = df_temp.iloc[-12:-1]["Low"].min()
            #     print(f"Processing stock: {stock['Symbol']}, High: {dh}, Low: {dl}, High Wick: {dhw}, Low Wick: {dlw}")
            #     print(f"11-candle High: {hX}, 11-candle Low: {lX}, 11-candle High Wick: {hwX}, 11-candle Low Wick: {lwX}")
            #     print(f"Processing stock: {stock['Symbol']}")
            #     detect_candlestick_pattern(first_3_candles, window, stock['Symbol'], lsize, dh, dl, dhw, dlw, hX, lX, hwX, lwX, round(float(stock['LotSize']) * 0.4))
            #     # print(f"waiting 10 second before next stock...")
            #     # time.sleep(10)
            # #=============

            # print(f"Processing stock: {stock['Symbol']}")
            detect_candlestick_pattern(first_3_candles, df, stock['Symbol'], lsize, dh, dl, dhw, dlw, hX, lX, hwX, lwX, round(float(stock['LotSize']) * 0.4))
        except Exception as e:
            print(stock["Symbol"], e)

    # print("DOWNLOAD COMPLETE")
#===================TEST===================================
#login to API
from api_helper import NorenApiPy

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
#=================================================
process_buy_sell(api)