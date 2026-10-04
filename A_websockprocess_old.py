from datetime import datetime, timedelta
import pandas as pd
import os
import json
import yaml
import logging
import redis
from api_helper import NorenApiPy

#==========================================================
# Login 
#==========================================================
#start of our program
api = NorenApiPy()
##yaml for parameters
with open('cred.yml') as f:
    cred = yaml.load(f, Loader=yaml.FullLoader)
    print(cred)

#ret = api.login(userid = cred['user'], password = cred['pwd'], twoFA=cred['factor2'], vendor_code=cred['vc'], api_secret=cred['apikey'], imei=cred['imei'])
ret = api.injectOAuthHeader(cred['Access_token'],cred['UID'],cred['Account_ID'])

if ret != None:    
    print("Login successful")
else:
    print("Login failed")
    exit()

# Set credentials safely
api.set_credentials(cred['Access_token'],cred['UID'],cred['Account_ID'])
#==========================================================
webSocketData = {}
redisObject = redis.Redis(host='localhost', port=6379, db=0)

# Handle incomming feed
def event_handler_feed_update(feed):
    # print(f"[{datetime.now()}] Market Feed Update: {feed}")
    latest_key = f"HTA:{feed['tk']}"
    updateData = False

    if feed["tk"] not in webSocketData:
        webSocketData[feed["tk"]] = feed.copy()
        updateData = True
    else:
        if "lp" in feed:
            updateData = True
            webSocketData[feed["tk"]]["lp"] = feed["lp"]

        if "h" in feed:
            updateData = True
            webSocketData[feed["tk"]]["h"] = feed["h"]

        if "l" in feed:
            updateData = True
            webSocketData[feed["tk"]]["l"] = feed["l"]

        if "pc" in feed:
            updateData = True
            webSocketData[feed["tk"]]["pc"] = feed["pc"]

    if updateData:
        # Add current server time
        webSocketData[feed["tk"]]["updated_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        latest_feed = json.dumps(webSocketData[feed["tk"]])
        # Store latest snapshot
        redisObject.set(latest_key, latest_feed)


#application callbacks
def event_handler_order_update(message):
    print("order event: " + str(message))

# handle connection open call back
def socket_open_callback():
    print(f"[{datetime.now()}] WebSocket connection opened.")

    try:
        # df = pd.read_csv("NIFTY50_Tokens.csv")
        # tokens = [f"NSE|{int(t)}" for t in df["Token"]]
        # api.subscribe(tokens)
        ret = api.subscribe('NSE|26000')
        print(f"[{datetime.now()}] Subscribe result: {ret}")
    except Exception as e:
        print(f"[{datetime.now()}] Subscribe ERROR: {e}")


# Handle connection close call back
def socket_close_callback():
    print(f"[{datetime.now()}] WebSocket connection closed.")
    
 
# start WebSocket connection
wsk = api.start_websocket(
    subscribe_callback=event_handler_feed_update,
    order_update_callback=event_handler_order_update, 
    socket_open_callback=socket_open_callback, 
    socket_close_callback=socket_close_callback)
# print(wsk)

# Keep the script running to listen for WebSocket messages
try:
    while True:
        
        now = datetime.now()
        current_minutes = now.hour * 60 + now.minute

        # Trading window: 09:15 to 15:15
        start_minutes = 9 * 60 + 14
        end_minutes = 15 * 60 + 14
        # print(f"current_minutes: {current_minutes}, start_minutes: {start_minutes}, end_minutes: {end_minutes}")
        if start_minutes <= current_minutes <= end_minutes:
            pass
        else:
            print(f"close web socket.")
            socket_close_callback()
            exit()
            
except KeyboardInterrupt:
    print("WebSocket connection closed.")
    exit()