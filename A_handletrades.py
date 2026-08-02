import subprocess
import sys
import time
from pathlib import Path
import shutil
import yaml
import pandas as pd
from datetime import datetime, timedelta
# ===========================================================
# Input NIFTY stocks
# ===========================================================
NIFTY = pd.read_csv("FNO_LotSize_Expiry.csv")
NIFTY = NIFTY.set_index("Symbol").to_dict("index")
#=======================================================
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
# VARIABLES
activePositions = {}
allOrders = {}
buyOpenOrders = {}
sellOpenOrders = {}
#=================================================
# Get all active positions
def getactivepositions():
    #--------------------------------------------------
    global activePositions
    # get positions
    activePositions = api.get_positions()
    print("==>activePositions: ", activePositions)

# Get orders and filter it
def getOrders():
    #--------------------------------------------------
    global allOrders
    global buyOpenOrders
    global sellOpenOrders
    # Get open orders
    allOrders = api.get_order_book()
    print("==>allOrders:", allOrders)
    # Check for API failure
    if isinstance(allOrders, dict):
        if orders.get("stat") != "Ok":
            print(f"API Error: {allOrders.get('emsg', 'Unknown error')}")
            return None
    elif allOrders == None:
        print(f"No Data")
        return None 
    # Open bug orders
    buyOpenOrders = {
        order["tsym"]: order
        for order in allOrders
        if order.get("status") == "Open"
        and order.get("trantype") == "B"
    }
    print("==>buyOpenOrders: ", buyOpenOrders)
    # Open Sell orders
    sellOpenOrders = {
        order["tsym"]: order
        for order in allOrders
        if order.get("status") == "Open"
        and order.get("trantype") == "S"
    }
    print("==>sellOpenOrders: ", sellOpenOrders)


# Cancel long open buy orders
def cancelBuyOrders():
    #----------------------------------------------------
    global buyOpenOrders
    # Cancel long open bug orders
    now = datetime.now()
    for order in buyOpenOrders:
        try:
            order_time = datetime.strptime(order["norentm"], "%d-%m-%Y %H:%M:%S")
            # Cancel bug order
            if now - order_time >= timedelta(minutes=5):
                print(f"Cancelling Order: {order['norenordno']}")
                resp = api.cancel_order(orderno=order["norenordno"])
                print(resp)
        except Exception as e:
            print(f"Error processing {order['norenordno']}: {e}")
    #------------------------------------------------------

# Close long open sell orders
def closeSellOrders():
    #----------------------------------------------------
    global sellOpenOrders
    # Cancel long open bug orders
    now = datetime.now()
    for order in sellOpenOrders:
        try:
            order_time = datetime.strptime(order["norentm"], "%d-%m-%Y %H:%M:%S")
            # Close Sell order
            if now - order_time >= timedelta(minutes=30):
                print(f"Closing Order: {order['norenordno']}")
                ret = api.modify_order(exchange=order['exch'], tradingsymbol=order['tsym'], 
                                        orderno=order["norenordno"], newquantity=order['qty'], 
                                        newprice_type='MKT', newprice=0.00)
        except Exception as e:
            print(f"Error processing {order['norenordno']}: {e}")

# Round off cost to 1 decimal place
def roundOffCost(val):
    #----------------------------------------------------
    # print("==>Val", val)
    txt = str(val).split(".")
    lVal = txt[0]  + "." + txt[1][slice(1)]
    # print("==>lVal", lVal)
    return float(lVal)


# Place sell order
def placeSellorder():
    #----------------------------------------------------
    global activePositions
    for pos in activePositions:
        print("==>", pos['symname'])
        cPrice = float(pos['netavgprc'])
        tPrice = roundOffCost(cPrice + (0.4*NIFTY[pos['symname']]['StrikeDiff'])-1)
        lPrice = roundOffCost(cPrice - (0.2*NIFTY[pos['symname']]['StrikeDiff'])+1)
        print("====>Target Price: ", str(tPrice))
        print("====>Stop Loss Price: ", str(lPrice))
        # Fresh sell order
        if pos['tsym'] not in sellOpenOrders:
            try:
                api.place_order(buy_or_sell='S', product_type='M',
                            exchange=pos['exch'], tradingsymbol=pos['tsym'], 
                            quantity=pos['netqty'], discloseqty=0, 
                            price_type='LMT', price=tPrice, trigger_price=tPrice,
                            retention='DAY', remarks='HTA:LMT')
            except Exception as e:
                print(f"Error processing {order['norenordno']}: {e}")   
        # New quantity is different from the existing order quantity, modify the order 
        elif pos['netqty'] != sellOpenOrders[pos['tsym']]['qty']:
            print(f"Updating Order: {sellOpenOrders[pos['tsym']]['norenordno']}")
            try:
                api.modify_order(exchange=pos['exch'], tradingsymbol=pos['tsym'], 
                                orderno=sellOpenOrders[pos['tsym']]["norenordno"], 
                                newquantity=pos['netqty'], newprice_type='LMT', 
                                newprice=tPrice, newtrigger_price=tPrice)
            except Exception as e:
                print(f"Error processing {order['norenordno']}: {e}")


# def getlimits():
#     ret = api.get_limits()
#     print(ret)
   
getactivepositions()
getOrders()
closeSellOrders()
placeSellorder()

#=================================================
INTERVAL = 1 * 60  # 5 minutes
while True:
    now = datetime.now()
    current_minutes = now.hour * 60 + now.minute

    # Trading window: 09:15 to 15:30
    start_minutes = 9 * 60 + 15
    end_minutes = 15 * 60 + 25
    if start_minutes <= current_minutes <= end_minutes:
        loop_start = time.time()
        
        try:
            # handle trades
            getactivepositions()
            getOrders()
            closeSellOrders()
            placeSellorder()

        except subprocess.CalledProcessError as e:
            print(f"Script failed: {e}")

        # Calculate remaining time in the 5-minute window
        elapsed = time.time() - loop_start
        wait_time = max(0, INTERVAL - elapsed)

        if wait_time > 0:
            print(f"Waiting {wait_time:.1f} seconds until next run...")
            time.sleep(wait_time)
        else:
            print("Processing took longer than 5 minutes. Starting next run immediately.")
    else:
        print("Outside trading hours. Waiting until next trading window...")
        exit()  # Exit the script if outside trading hours