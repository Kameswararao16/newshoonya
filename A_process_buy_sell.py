from datetime import datetime, timedelta
import pandas as pd
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
# #----------------------------
# # Read previous day data from history
# folder = Path("nifty100_data")
# previous_day_data = {}

# for file in folder.glob("*.csv"):
#     try:
#         df = pd.read_csv(file)
#         if df.empty: continue

#         # Make sure data is sorted by Date
#         df["Date"] = pd.to_datetime(df["Date"])
#         df = df.sort_values("Date")

#         # Get latest candle
#         latest = df.iloc[-1]

#         # Stock name from filename
#         stock_name = file.stem

#         previous_day_data[stock_name] = {
#             "Date": latest["Date"],
#             "Open": latest["Open"],
#             "High": latest["High"],
#             "Low": latest["Low"],
#             "Close": latest["Close"],
#             "Volume": latest["Volume"]
#         }

#     except Exception as e:
#         print(f"Error reading {file}: {e}")

# print(previous_day_data)
# #------------------------------
#redis
redisObject = redis.Redis(host='localhost', port=6379, db=0)
key = "HTA:Buy"
#====================================================================
# Detect candlestick patterns
def detect_candlestick_pattern(first_3_candles, last_5_candles, candles, stkname, lsize, dh, dl, dhw, dlw, hX, lX, hwX, lwX, minmovement):

    if len(candles) < 2:
        print("Not enough candles to detect patterns")
        return None

    #-----------------------------------------
    # Get trend based on last 5 candles
    l5_high = last_5_candles["High"].max()
    l5_low = last_5_candles["Low"].min()
    l5_close = last_5_candles["Close"].iloc[-1]
    l5_range = round(l5_high - l5_low, 2)
    print(f"Last 5 candles - High: {l5_high}, Low: {l5_low}, Close: {l5_close}, Range: {l5_range}")
    trend = "SIDE"
    if l5_range >= (0.4 * lsize):
        print(f"Last 5 candles range is more than 50% of lot size, determining trend...")
        if(l5_close > l5_high - (0.25 * l5_range)):
            trend = "UP"
        elif(l5_close < l5_low + (0.25 * l5_range)):
            trend = "DOWN"
    print(f"Trend based on last 5 candles: {trend}")
    #-----------------------------------------

    print(f"first_3_candles: {first_3_candles}")
    f_dhw = first_3_candles["High"].max()
    # if (previous_day_data[stkname]['Close'] > f_dhw): f_dhw = previous_day_data[stkname]['Close']
    f_dlw = first_3_candles["Low"].min()
    # if (previous_day_data[stkname]['Close'] < f_dlw): f_dlw = previous_day_data[stkname]['Close']
    f_dh = first_3_candles[["Open", "Close"]].max().max()
    f_dl = first_3_candles[["Open", "Close"]].min().min()
    c1 = (first_3_candles.iloc[0]["Close"] - first_3_candles.iloc[0]["Open"]) 
    c2 = (first_3_candles.iloc[1]["Close"] - first_3_candles.iloc[1]["Open"])
    c3 = (first_3_candles.iloc[2]["Close"] - first_3_candles.iloc[2]["Open"])
    print(f"First 3 candles - c1: {c1}, c2: {c2}, c3: {c3}")
    #--------------------------------------------
    # Get Direction bias based on first 3 candles
    bias = "SIDE"
    bias_color = ("GREEN" if c1+c2+c3 > 0 else "RED")
    bias_boundary = first_3_candles.iloc[0]["Open"] + c1+c2+c3  # Not used
    print(f"bias_color: {bias_color}, bias_boundary: {bias_boundary}")
    if (abs(f_dh - f_dl) > (0.8 *lsize)):
        print(f"enough movement to consider.")
        if (c1+c2+c3 >  (0.3 *lsize)): 
            bias = "UP" 
        elif (c1+c2+c3 < -(0.5 *lsize)): 
            bias = "DOWN"
    print(f"Bias based on first 3 candles: {bias}")
    # Get time
    #now = datetime.now().strftime("%H:%M:%S")
    #Test
    now = candles.iloc[-1]["Date"].strftime("%H:%M:%S")
    # ---------------- 
    if now > "11:30:00":
        print(f"bias reversal.")
        if abs(dh-float(candles.iloc[-1]["High"])) < round(0.25 * lsize, 2):
            print(f"Reached day high. So, bias NONE.")
            bias = "NONE"
        else:
            print(f"bias reversal.")
            if bias == "UP":
                bias = "DOWN"
            elif bias == "DOWN":
                bias = "UP"
    print(f"Bias after time check: {bias}")
    #-------------------------------------
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
    c_mid = (c_high + c_low)/2
    c_body = round(abs(cc - co), 2)
    c_upper_wick = round(ch - max(co, cc), 2)
    c_lower_wick = round(min(co, cc) - cl, 2)
    c_range = round(ch - cl, 2)
    print(f"c_high: {c_high}, c_low: {c_low}, c_body: {c_body}, c_upper_wick: {c_upper_wick}, c_lower_wick:  {c_lower_wick}, c_range: {c_range}")

    # Body should be at least 60% of the entire candle
    # pstrong_body = p_body >= 0.4 * p_range
    # cstrong_body = c_body >= 0.5 * c_range

    # Add check last candle is either at high or low
    buffer = round(0.25 * lsize, 2)
    print(f"Buffer: {buffer}")

    last_candle_at_fhigh = abs(max(cc, co) - f_dh) <= buffer
    last_candle_at_flow = abs(min(cc, co) - f_dl) <= buffer
    last_candle_at_fhigh_wick = abs(max(ch, cl) - f_dh) <= buffer
    last_candle_at_flow_wick = abs(min(ch, cl) - f_dl) <= buffer
    #--------------First candle logic ----------------------------
    buy_signal = False
    sell_signal = False
    entry = cc
    target = 0.5 * lsize
    stop_loss = 0.5 * lsize
    now = curr["Date"]
    c_red_candle = (cc < co)
    c_green_candle = (cc > co)
    print(f"c_red_candle: {c_red_candle}, c_green_candle: {c_green_candle}")
    c_strong_lower_wick = (c_lower_wick > (0.7 * c_body))
    c_strong_upper_wick = (c_upper_wick > (0.7 * c_body))
    c_strong_body = c_body >= (0.35 * c_range)
    print(f"c_strong_lower_wick: {c_strong_lower_wick}, c_strong_upper_wick: {c_strong_upper_wick}, c_strong_body: {c_strong_body}")
    #------------------------Pattern Indentification---------------------
    # Marubozu
    marubozu = (c_body >= 0.89 * c_range)
    print(f"marubozu: {marubozu}")
    # Shooting Star - Bearish
    shooting_star = (
        (c_upper_wick >= 0.50 * c_range and c_body >= 0.1 * c_range and c_red_candle)    # not a doji
        or
        (c_upper_wick > (0.7 * c_range))
    )
    print(f"shooting_star: {shooting_star}")
    # Hammer- Bullish
    hammer = (
        (c_lower_wick >= 0.50 * c_range and c_body >= 0.1 * c_range and c_green_candle)    # not a doji
        or
        (c_lower_wick > (0.7 * c_range))
    )
    print(f"hammer: {hammer}")
    # Bullish Engulfing
    bullish_engulf =    (   c_strong_body and 
                            pc < po and
                            cc >= co and
                            ( (co <= pc+(0.03*lsize) and cc >= po) or
                            (co <= pc and cc+(0.03*lsize) >= po) )
    )
    print(f"bullish_engulf: {bullish_engulf}")
    # Bearish Engulfing
    bearish_engulf =    (   c_strong_body and
                            pc >= po and
                            cc <= co and
                            ( (co+(0.03*lsize) >= pc and cc <= po) or
                            (co >= pc and cc <= po+(0.03*lsize))  )
    )
    print(f"bearish_engulf: {bearish_engulf}")
    if(bullish_engulf and bearish_engulf):
        print(f"Both bullish and bearish engulfing detected. This is unexpected.")
        bullish_engulf = False
        bearish_engulf = False
    print(f"bullish_engulf: {bullish_engulf}, bearish_engulf: {bearish_engulf}")
    # Bullish confirmation
    bullish_confirmation = (
        # c_green_candle and
        (marubozu and c_green_candle) or    #   Marubo & Green candle
        bullish_engulf or                   #   Bullish Engulf
        (hammer  and c_green_candle)        #   Hammer
    )
    print(f"bullish_confirmation: {bullish_confirmation}")
    # Bearish conformation 
    bearish_confirmation = (
        # c_red_candle and 
        (marubozu and c_red_candle) or      #   Marubo & red candle
        bearish_engulf or                   #   Bearish Engulf
        (shooting_star  and c_red_candle)   #   shooting star  
    )
    print(f"bearish_confirmation: {bearish_confirmation}")

    #------------------------Actual Logic----------------------------
    # First candle logic
    # Current candle body is still above first 3-candle high
    if (min(cc, co) > f_dhw): 
        print(f"Price moved beyond first 3-candle high.")
        # Day high is more than first 3-candle high
        if(dh > (f_dhw + (0.5*lsize))):
            print(f"Days high is more to proceed.")
            # Current candle lower wick is near first 3-candle high (above or below) 
            if( (dh > (cc + (0.4*lsize))) and ( (abs(f_dhw - cl) <= round(0.25 * lsize, 2)) or (f_dhw > cl) )):
                print("Price retraced back to day high.")
                if (bullish_confirmation and trend != "UP"): # Bullish candle formed
                    print(f"BUY: Bullish confirmation.")
                    buy_signal = True
                    entry = entry - round(c_range*0.2, 2)
                    target = entry + round((0.5*lsize), 2)
                    stop_loss = entry - round((0.20*lsize), 2)
                    
            # Current candle higher wick near day's high
            # Current candle high is still below day's high
            elif( (f_dhw < (cc - (0.4*lsize))) and ((abs(dhw - ch) <= round(0.25 * lsize, 2)) or ( (dhw < ch) and (max(cc, co) < dhw)) )):
                print("Price is at day high.")
                if(bearish_confirmation and trend != "DOWN"): # Bearish candle formed
                    print(f"SELL: Bearish conformation")
                    sell_signal = True
                    entry = entry + round(c_range*0.2, 2)  
                    target = entry - round((0.5*lsize), 2)
                    stop_loss = entry + round((0.20*lsize), 2)
                           
    # Current candle body is still below 3-candle low
    elif(min(cc, co) < f_dlw):  
        print(f"Price moved beyond first 3-candle low.")
        # Day low is below than first 3-candle low with more than 50% of lot size
        if(dl < (f_dlw - (0.5*lsize))) : 
            print(f"Days low is more to proceed.")
            # Current candle higher wick is near first 3-candle low (above or below)
            if( (dl < (cc - (0.4*lsize)))  and  ((abs(f_dlw - ch) < round(0.25 * lsize, 2)) or (f_dlw < ch) )):
                print("Price retraced back to day low.")
                # Up trend + bearish confirmation + current candle close is still near first 3-candle low
                if(trend != "DOWN" and  (bearish_confirmation or (c_red_candle and (cc < f_dlw and co > f_dlw))) ):  
                    print(f"SELL: Bearish conformation")
                    sell_signal = True
                    entry = entry + round(c_range*0.2, 2)
                    target = entry - round((0.5*lsize), 2)
                    stop_loss = entry + round((0.20*lsize), 2)
                    
            # Current candle lower wick near day's low and  Current candle low is still above day's low
            elif( (f_dlw > (cc + (0.4*lsize))) and ((abs(dlw - cl) <= round(0.25 * lsize, 2)) or ( (dlw > cl) and (min(cc, co) > dlw)) )):
                print("Price is at day low.")
                # down trend + bullish confirmation + current candle close is still near day's low
                if( trend != "UP" and  (bullish_confirmation or (c_green_candle and (cc > f_dlw and co < f_dlw))) ):  
                    print(f"BUY: Bullish conformation")
                    buy_signal = True
                    entry = entry - round(c_range*0.2, 2)
                    target = entry + round((0.5*lsize), 2)
                    stop_loss = entry - round((0.20*lsize), 2)
                    
    # Current candle is inside first 3-candles and current candle is near first 3-candle high and range of first 3-candles is more than 50% of lot size
    if( (f_dhw+(0.25*lsize) > max(cc, co)) and (f_dlw-(0.25*lsize) < min(cc, co)) and (abs(f_dhw - f_dlw) > (0.5*lsize)) ):
        print(f"With in first 3-candles.")
        print(f"abs(f_dl - cc): {abs(f_dl - cc)},  round(0.25 * lsize, 2): {round(0.25 * lsize, 2)}")
        print(f"bias: {bias}, bearish_confirmation: {bearish_confirmation}, trend: {trend}")

        # Up trend + bearish confirmation + current candle close is still near first 3-candle high            
        trigger_sell_signal =  False
        trigger_buy_signal =  False
        # Current candle closed near 1st 3 candle's high(wick)
        if ( (abs(cc - f_dhw) < round(0.25 * lsize, 2)) and (cc < f_dhw) ) : 
            print(f"Normal sell checks")
            trigger_sell_signal = True
        # Bias is DOWN + Near 1st 3 candle's low with/witout wick
        elif(bias != "UP" and  bias_color == "RED" and dlw < f_dlw and cc < f_dl and 
            (abs(cc - f_dlw) < round(0.25 * lsize, 2) or abs(cc - f_dl) < round(0.25 * lsize, 2) ) ): 
            print(f"Bias sell checks")
            trigger_sell_signal = True

        # Current candle closed near 1st 3 candle's low(wick)
        if ( (abs(cc - f_dlw) < round(0.25 * lsize, 2)) and (cc > f_dlw)): 
            print(f"Normal buy checks")
            trigger_buy_signal = True
        # Bias is UP + Near 1st 3 candle's high with/witout wick
        elif(bias != "DOWN" and bias_color == "GREEN" and dhw > f_dhw and cc > f_dh and 
            ((abs(cc - f_dhw) < round(0.25 * lsize, 2) and cc > f_dhw) or abs(cc - f_dh) < round(0.25 * lsize, 2) )): 
            print(f"Bias buy checks")
            trigger_buy_signal = True

        # trend not DOWN + bearish confirmation + sell signal
        if(bearish_confirmation and trend != "DOWN" and  trigger_sell_signal):
            print(f"SELL: Bearish conformation")
            sell_signal = True
            entry = entry + round(c_range*0.2, 2)
            target = entry - round((0.5*lsize), 2)
            stop_loss = entry + round((0.20*lsize), 2)
        # trend not UP + bullish confirmation + sell signal
        if(bullish_confirmation and trend != "UP" and  trigger_buy_signal):    
            print(f"BUY : Bullish confirmation.")
            buy_signal = True
            entry = entry - round(c_range*0.2, 2)
            target = entry + round((0.5*lsize), 2)
            stop_loss = entry - round((0.20*lsize), 2)

                
    # Send message
    signal_type = None
    if(sell_signal == True):
        signal_type = "SELL"
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
        signal_type = "BUY"
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
    if(stkname == "NIFTY50" and signal_type != None):
        # Store in redis
        signal_data = {
                "symbol": stkname,
                "signal": signal_type,
                "entry_price": str(entry),
                "stop_loss": str(stop_loss),
                "target_price": str(target),
                "entry_time": str(now)
            }
        redisObject.set(key, json.dumps(signal_data))
        # Test
        buyData = json.loads(redisObject.get(key))
        print(f"buyData: {buyData}")
    return None
   

# =========================================================
# Process all stocks and detect patterns
# =========================================================
def process_buy_sell(api):
    print("Starting to process all stocks for buy/sell signals...")
    # time.sleep(5)  # Wait for 5 seconds before starting
    for stock in NIFTY:
        # process only NIFTY
        if stock['Symbol'] != "NIFTY50" : 
            continue

        lsize = float(stock['LotSize'])
        try:
            file = os.path.join( DATA_FOLDER, stock["Symbol"]+".csv")
            if not os.path.exists(file):
                print(stock["Symbol"], "missing data")
                continue

            df = pd.read_csv(file)
            df["Date"] = pd.to_datetime(df["Date"], dayfirst=True)
            df = df.sort_values("Date")
            # wait for first 3 candles
            if len(df)<4: 
                print(f"Not enough data to process {stock['Symbol']}")
                continue
            first_3_candles = df.iloc[:3]
            last_5_candles = df.iloc[max(0, len(df)-6):len(df)-1]
            print(f"last_5_candles: {last_5_candles}")         

            #-----------------------------------------------
            dh = (df[["Open","Close"]]).max().max()
            dl = (df[["Open","Close"]]).min().min()
            dhw = df["High"].max()
            dlw = df["Low"].min()
            hX = df.iloc[max(0, len(df)-12):len(df)-1][["Open", "Close"]].max().max()
            lX = df.iloc[max(0, len(df)-12):len(df)-1][["Open", "Close"]].min().min()
            hwX = df.iloc[max(0, len(df)-12):len(df)-1]["High"].max()
            lwX = df.iloc[max(0, len(df)-12):len(df)-1]["Low"].min()
            print(f"Processing stock: {stock['Symbol']}, High: {dh}, Low: {dl}, High Wick: {dhw}, Low Wick: {dlw}")
            print(f"11-candle High: {hX}, 11-candle Low: {lX}, 11-candle High Wick: {hwX}, 11-candle Low Wick: {lwX}")
            df = (df.sort_values("Date").tail(3))

            # #====test=====
            # print(f"df: {len(df)}")

            # for i in range(3, len(df) - 1):
            #     window = df.iloc[i-2:i]
            #     last_5_candles = df.iloc[max(0, i-6):i-1]
            #     print(f"last_5_candles: {last_5_candles}") 
            #     df_temp = df.iloc[0:max(0, i-1)]
            #     dh = (df_temp[["Open","Close"]]).max().max()
            #     dl = (df_temp[["Open","Close"]]).min().min()
            #     dhw = df_temp["High"].max()
            #     dlw = df_temp["Low"].min()
            #     hX = df_temp.iloc[max(0, i-12):i][["Open", "Close"]].max().max()
            #     lX = df_temp.iloc[max(0, i-12):i][["Open", "Close"]].min().min()
            #     hwX = df_temp.iloc[max(0, i-12):i]["High"].max()
            #     lwX = df_temp.iloc[max(0, i-12):i]["Low"].min()
            #     print(f"Processing stock: {stock['Symbol']}, High: {dh}, Low: {dl}, High Wick: {dhw}, Low Wick: {dlw}")
            #     print(f"11-candle High: {hX}, 11-candle Low: {lX}, 11-candle High Wick: {hwX}, 11-candle Low Wick: {lwX}")
            #     print(f"Processing stock: {stock['Symbol']}")
            #     detect_candlestick_pattern(first_3_candles, last_5_candles, window, stock['Symbol'], lsize, dh, dl, dhw, dlw, hX, lX, hwX, lwX, round(float(stock['LotSize']) * 0.4))
            #     # print(f"waiting 10 second before next stock...")
            #     # time.sleep(10)
            # #=============

            # print(f"Processing stock: {stock['Symbol']}")
            detect_candlestick_pattern(first_3_candles, last_5_candles, df, stock['Symbol'], lsize, dh, dl, dhw, dlw, hX, lX, hwX, lwX, round(float(stock['LotSize']) * 0.4))
        except Exception as e:
            print(stock["Symbol"], e)

    # print("DOWNLOAD COMPLETE")
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
# process_buy_sell(api)