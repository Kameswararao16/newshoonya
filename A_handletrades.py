import subprocess
import sys
import time
from pathlib import Path
import shutil
import yaml
import pandas as pd
from datetime import datetime, timedelta
import redis
import json

# ===========================================================
# Input NIFTY stocks
# ===========================================================
NIFTYALL = pd.read_csv("FNO_LotSize_Expiry.csv")
NIFTYALL = NIFTYALL.set_index("Symbol").to_dict("index")

redisObject = redis.Redis(host='localhost', port=6379, db=0)
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
allOrders = {}
buyOpenOrders = {}
sellOpenOrders = {}
activePositions = {}
daysMTM = 0.0

#=================================================
# Get all active positions
def getactivepositions():
    #--------------------------------------------------
    global activePositions
    global daysMTM

    # get positions
    positions = api.get_positions()
    print("==>positions: ", positions)
    activePositions.clear()
    daysMTM = 0.0
    if positions != None: 
        # Get days profit/loss
        for i in positions:
            if((int(i["netqty"])) > 0):                    
                activePositions[i["tsym"]] = i   
            if((i["instname"] == "OPTSTK") or i["instname"] == "OPTIDX"):
                daysMTM += float(i['urmtom']) + float(i['rpnl'])
    print(f'{daysMTM} is your Daily MTM')
    print(f"==>Active position: {activePositions} ")


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
        if order.get("status") == "OPEN"
        and order.get("trantype") == "B"
    }
    print("==>buyOpenOrders: ", buyOpenOrders)
    # Open Sell orders
    sellOpenOrders = {
        order["tsym"]: order
        for order in allOrders
        if order.get("status") == "OPEN"
        and order.get("trantype") == "S"
    }
    print("==>sellOpenOrders: ", sellOpenOrders)


# Cancel long open buy orders
def cancelBuyOrders():
    #----------------------------------------------------
    global buyOpenOrders
    # Cancel long open bug orders
    now = datetime.now()
    for order in buyOpenOrders.values():
        try:
            order_time = datetime.strptime(order["norentm"], "%H:%M:%S %d-%m-%Y")
            # Cancel bug order
            if now - order_time >= timedelta(minutes=5):
                print(f"Cancelling Order: {order['norenordno']}")
                resp = api.cancel_order(orderno=order["norenordno"])
                print(resp)
        except Exception as e:
            print(f"Error processing {order['norenordno']}: {e}")  
    #------------------------------------------------------


# Close long open sell orders or order which are in loss beyond limit
def closeSellOrders():
    #----------------------------------------------------
    global sellOpenOrders
    global activePositions
    # Cancel long open bug orders
    now = datetime.now()
    for order in sellOpenOrders.values():
        try:
            # Check if the price is manually overriden
            pInd = order['prc'].find(".")
            if( (pInd > 0) and (pInd+2 <= len(order['prc'])) and (order['prc'][pInd+2] == "5") ): 
                print(f"Manually Overridden.")
                continue # Manual overridden

            order_time = datetime.strptime(order["norentm"], "%H:%M:%S %d-%m-%Y")
            # Close Sell order
            print(float(order['qty']))
            print(order['tsym'])
            print(NIFTYALL[order['symname']]['StrikeDiff'] )
            print(float(activePositions[order['tsym']]['urmtom']))
            lossTol = float(order['qty']) * -0.15*NIFTYALL[order['symname']]['StrikeDiff'] 
            print(f"loss tolerence: {lossTol}")
            if ((now - order_time >= timedelta(minutes=40)) or
                (lossTol > float(activePositions[order['tsym']]['urmtom'])) ) :
                # print(f"Closing Order: {order['norenordno']}")
                # # Cancel the existing order and place a new order with market price
                # ret = api.cancel_order(orderno=order["norenordno"])
                # print(ret)
                print(f"Market order for {order['tsym']} due to time or loss limit exceeded.")
                nPrice = roundOffCost(float(activePositions[order['tsym']]['lp']))
                print(f"New Price: {nPrice}")
                # place a market order to close the position                
                ret = api.modify_order(exchange=activePositions[order['tsym']]['exch'], 
                                        tradingsymbol=activePositions[order['tsym']]['tsym'], 
                                        orderno=sellOpenOrders[activePositions[order['tsym']]['tsym']]["norenordno"], 
                                        newquantity=activePositions[order['tsym']]['netqty'], newprice_type='LMT', 
                                        newprice=nPrice, newtrigger_price=nPrice)
                print(ret)

        except Exception as e:
            print(f"Error processing {order['norenordno']}: {e}")


# Round off cost to 1 decimal place
def roundOffCost(val):
    #----------------------------------------------------
    txt = str(val).split(".")
    lVal = txt[0]  + "." + txt[1][slice(1)]
    return float(lVal)


# Place sell order
def placeSellorder():
    #----------------------------------------------------
    global activePositions
    global sellOpenOrders
    for pos in activePositions:
        print("==>", pos)
        print(f"Active Position Symbol parent: {activePositions[pos]['symname']}")
        if activePositions[pos]['symname'] not in NIFTYALL:
            print(f"Symbol {pos} not found in NIFTYALL. Skipping...")
            continue
        bPrice = float(activePositions[pos]['netavgprc'])
        tolerence = 0.15*NIFTYALL[activePositions[pos]['symname']]['StrikeDiff']
        tPrice = roundOffCost(bPrice - tolerence)
        print("====>SL LMT Price: ", str(tPrice))

        cPrice = float(activePositions[order['tsym']]['lp'])
        diff = cPrice - bPrice
        print(f"Current Price: {cPrice}, Buy Price: {bPrice}, Diff: {diff}, Tolerence: {tolerence}")
        blocks = diff // tolerence
        print(f"Blocks: {blocks}")
        # Fresh sell order
        if pos not in sellOpenOrders:
            print(f"Placing Sell Order for {pos}")
            try:
                ret = api.place_order(buy_or_sell='S', product_type=activePositions[pos]['prd'],
                            exchange=activePositions[pos]['exch'], tradingsymbol=activePositions[pos]['tsym'], 
                            quantity=activePositions[pos]['netqty'], discloseqty=0, 
                            price_type='SL_LMT', price=tPrice, trigger_price=tPrice,
                            retention='DAY', remarks='HTA:SL_LMT')

                print(f"Placed Sell Order: {ret}")
            except Exception as e:
                print(f"Error processing:{e}")   

        # New quantity is different from the existing order quantity, modify the order 
        elif activePositions[pos]['netqty'] != sellOpenOrders[activePositions[pos]['tsym']]['qty']:
            print(f"Updating Order: {sellOpenOrders[activePositions[pos]['tsym']]['norenordno']}")
            try:
                api.modify_order(exchange=activePositions[pos]['exch'], tradingsymbol=activePositions[pos]['tsym'], 
                                orderno=sellOpenOrders[activePositions[pos]['tsym']]["norenordno"], 
                                newquantity=activePositions[pos]['netqty'], newprice_type='SL_LMT', 
                                newprice=tPrice, newtrigger_price=tPrice)
            except Exception as e:
                print(f"Error processing {order['norenordno']}: {e}")

        # Enough profit, close order
        elif ( cPrice > (bPrice + (2.8*tolerence)) ):
            print(f"Close order: {sellOpenOrders[activePositions[pos]['tsym']]['norenordno']}")
            try:
                api.modify_order(exchange=activePositions[pos]['exch'], tradingsymbol=activePositions[pos]['tsym'], 
                                orderno=sellOpenOrders[activePositions[pos]['tsym']]["norenordno"], 
                                newquantity=activePositions[pos]['netqty'], newprice_type='LMT', 
                                newprice=cPrice, newtrigger_price=cPrice)

            except Exception as e:
                print(f"Error processing {order['norenordno']}: {e}")

        # Price moved to next block of tolerence, modify the order with updated price
        elif ( (cPrice > bPrice)  and (cPrice > (float(sellOpenOrders[activePositions[pos]['tsym']]['prc']) + (2*tolerence))) ):
            print(f"Updating Order Price: {sellOpenOrders[activePositions[pos]['tsym']]['norenordno']}")
            cPrice = roundOffCost(cPrice - tolerence)
            try:
                api.modify_order(exchange=activePositions[pos]['exch'], tradingsymbol=activePositions[pos]['tsym'], 
                                orderno=sellOpenOrders[activePositions[pos]['tsym']]["norenordno"], 
                                newquantity=activePositions[pos]['netqty'], newprice_type='SL_LMT', 
                                newprice=tPrice, newtrigger_price=tPrice)
            except Exception as e:
                print(f"Error processing {order['norenordno']}: {e}")


# Method to round-off to its nearst block size
def roundOffToNearstblokSize(value, block):
    #----------------------------------------------------
    #print(value, block)
    wNo100 = (value // 100) *100
    wNo10 = (value // 10) *10
    dNo1 = (value % 10)
    dNo2 = (value % 100)
    wNo = 0 
    #print(wNo100, wNo10, dNo1, dNo2)
    #print(dNo)
    if(block == 100):
        wNo = wNo100
        if(dNo2 > 50): wNo = wNo + 100   
    elif(block == 50):
        wNo = wNo100
        if(dNo2 > 25): wNo = wNo + 50
        if(dNo2 > 75): wNo = wNo + 50
    elif(block == 25):
        wNo = wNo100
        if(dNo2 > 12): wNo = wNo + 25
        if(dNo2 > 37): wNo = wNo + 25
        if(dNo2 > 62): wNo = wNo + 25
        if(dNo2 > 87): wNo = wNo + 25
    if(block == 20):
        wNo = wNo100
        if(dNo2 > 10): wNo = wNo + 20
        if(dNo2 > 30): wNo = wNo + 20
        if(dNo2 > 50): wNo = wNo + 20
        if(dNo2 > 70): wNo = wNo + 20
        if(dNo2 > 90): wNo = wNo + 20
    if(block == 10):
        wNo = wNo10
        if(dNo1 > 5): wNo = wNo + 10
    elif(block == 5):
        wNo = wNo10
        if(dNo1 > 2): wNo = wNo + 5
        if(dNo1 > 7): wNo = wNo + 5
    #print(wNo) 
    return wNo


# Place new buy orders based on the options generated by the algorithm 
def buyNewPositions():
    #----------------------------------------------------
        global buyOpenOrders
        global activePositions 
        global sellOpenOrders
        print("Buy options")
        key = "HTA:Buy"
        buyData = json.loads(redisObject.get(key))
        print(f"buy Data: {buyData}")
        bOptions = {}
        if(buyData != None): 
            # Data available
            now = datetime.now()
            print(f"buy options: {buyData}")
            entry_time = datetime.strptime(buyData["entry_time"], "%Y-%m-%d %H:%M:%S")
            elapsed = now - entry_time
            print(elapsed)
            if elapsed.total_seconds() < 600:
                tPrice = roundOffToNearstblokSize(float(buyData['entry_price']), 50)
                print(f"tPrice: {tPrice}")
                pSym = "NIFTY" if buyData["symbol"] == "NIFTY50" else buyData["symbol"]
                print(pSym)
                # print(NIFTYALL.keys())
                tSym = (
                    pSym
                    + NIFTYALL[pSym]["Expiry"]
                    + ("C" if buyData["signal"] == "BUY" else "P")
                    + str(int(tPrice))
                )
                print(tSym)
                optChain = api.get_option_chain(exchange="NFO", tradingsymbol=tSym, strikeprice=tPrice, count=1)
                print(f"Option Chain: {optChain}")
                # Get right token & lot size
                tkn = 0
                lsz = 0
                for i in optChain["values"]:
                    if (i["tsym"] == tSym):
                        tkn = i["token"]
                        lsz = i["ls"]
                # Get quotes
                print(f"token: {tkn}, lot size: {lsz}")
                optQuotes = api.get_quotes(exchange="NFO", token=tkn)
                print(f"Option Quotes: {optQuotes}")
                key = "HTA:26000"
                print(f"key: {key}")
                sData = json.loads(redisObject.get(key))
                print(f"Stock Quotes: {sData}")
                print(f"Stock Price: {sData['lp']}, Entry Price: {buyData['entry_price']}")
                diff = abs(float(sData["lp"]) - float(buyData['entry_price']))
                print(f"Diff: {diff}")
                bPrice = (float(optQuotes["lp"]) - diff/2) if buyData["signal"] == "BUY" else (float(optQuotes["lp"]) - diff/2)                
                bPrice = roundOffCost(bPrice)
                print(f"Buy Price: {bPrice}")
                # Get Account details
                aLimits = api.get_limits()
                print(f"Account Limits: {aLimits}")
                rpnl = (0.0 if "rpnl" not in aLimits else float(aLimits["rpnl"]))
                cash = float(aLimits["cash"]) + float(aLimits["payin"])
                mNeed = bPrice*NIFTYALL[pSym]['LotSize']
                print("Available Cash:" + str(cash))
                print("Required Cash:" + str(mNeed))
                print("Todays Profit/Loss:" + str(rpnl))
                if(tSym in activePositions):
                    try:
                        api.modify_order(exchange=activePositions[pos]['exch'], tradingsymbol=activePositions[pos]['tsym'], 
                                        orderno=sellOpenOrders[activePositions[pos]['tsym']]["norenordno"], 
                                        newquantity=activePositions[pos]['netqty'], newprice_type='LMT', 
                                        newprice=float(activePositions[pos]['netavgprc'])+0.1, 
                                        newtrigger_price=float(activePositions[pos]['netavgprc'])+0.1)
                    except Exception as e:
                        print(f"Error processing: {e}") 

                elif(rpnl >= -1000):
                    print("Profit/Loss is within limits.")
                    # Cash available + neither purchased nor placed a purchase order
                    if (cash > mNeed) and (tSym not in buyOpenOrders) and (tSym not in activePositions): 
                        try:
                            api.place_order(buy_or_sell='B', product_type='M',
                                        exchange='NFO', tradingsymbol=tSym, 
                                        quantity=NIFTYALL[pSym]['LotSize'], discloseqty=0, 
                                        price_type='LMT', price=bPrice, trigger_price=None,
                                        retention='DAY', remarks='HTA:LMT')
                        except Exception as e:
                            print(f"Error processing: {e}")   
                    else:
                        print("Insufficient funds to place the order.")
                else:
                    print("Days Loss limit reached.")


#=================================================
INTERVAL = 1 * 60  # 5 minutes
while True:
    now = datetime.now()
    current_minutes = now.hour * 60 + now.minute

    # Trading window: 09:15 to 15:15
    start_minutes = 9 * 60 + 16
    end_minutes = 15 * 60 + 14
    if start_minutes <= current_minutes <= end_minutes:
        loop_start = time.time()
        
        try:
            # handle trades
            getactivepositions()
            getOrders()
            cancelBuyOrders()
            placeSellorder()
            closeSellOrders()
            buyNewPositions()

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