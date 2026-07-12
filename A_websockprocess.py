from datetime import datetime, timedelta
import pandas as pd
import os
import json
import yaml
import logging
import redis

from api_helper import NorenApiPy

#sample
# logging.basicConfig(level=logging.DEBUG)

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
# Define callback functions for WebSocket events
# def event_handler_feed_update(feed):
#     print("Market Feed Update:", feed)
#     key = "HavyaTej:" + feed["tk"]
#     updateData = False
#     if feed["tk"] not in webSocketData:
#        webSocketData[feed["tk"]] = feed
#        updateData = True
#        #print(feed)
#     else:
#         # print("+++", webSocketData[feed["tk"]])
#         if "lp" in feed:
#           updateData = True
#         #   print("update lp: ", feed["lp"] )
#           webSocketData[feed["tk"]]["lp"] = feed["lp"]  
#         if "h" in feed:
#           updateData = True
#         #   print("update h:", feed["h"] )
#           webSocketData[feed["tk"]]["h"] = feed["h"] 
#         if "l" in feed:
#           updateData = True
#         #   print("update l: ", feed["l"] )
#           webSocketData[feed["tk"]]["l"] = feed["l"] 
#         if "pc" in feed:
#           updateData = True
#         #   print("update l: ", feed["l"] )
#           webSocketData[feed["tk"]]["pc"] = feed["pc"] 
#     # print(key)
#     if(updateData == True):
#         print("===", webSocketData[feed["tk"]])
#         redisObject.set(key, json.dumps(webSocketData[feed["tk"]]))
#     # time.sleep(1)    
#     print(key)
#     print("==>", redisObject.get(key))
import json

def event_handler_feed_update(feed):
    print("Market Feed Update:", feed)
    now = datetime.now()
    print("Current Time:", now.strftime("%Y-%m-%d %H:%M:%S"))
    latest_key = f"HavyaTej:{feed['tk']}"
    # history_key = f"HavyaTej:{feed['tk']}:history"

    updateData = False

    if feed["tk"] not in webSocketData:
        webSocketData[feed["tk"]] = feed
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
        latest_feed = json.dumps(webSocketData[feed["tk"]])

        # Store latest snapshot
        redisObject.set(latest_key, latest_feed)
        print(f"Updated Redis key: {latest_key} with latest feed.")
        now = datetime.now()
        print("Current Time:", now.strftime("%Y-%m-%d %H:%M:%S"))
        # Append to history
        # redisObject.rpush(history_key, latest_feed)

        # Keep only last 10,000 updates (optional)
        # redisObject.ltrim(history_key, -10000, -1)

        # print("Latest:", latest_feed)

    # print("Latest Key:", latest_key)
    # print("History Key:", history_key)

#application callbacks
def event_handler_order_update(message):
    print("order event: " + str(message))

def socket_open_callback():
    print("WebSocket connection opened.")

    df = pd.read_csv("NIFTY50_Tokens.csv")
    tokens = [f"NSE|{int(t)}" for t in df["Token"]]
    api.subscribe(tokens)
    print(f"Subscribed to {len(tokens)} tokens.")
    # api.subscribe('NSE|26000')
    #api.subscribe(['NSE|22', 'BSE|522032'])

def socket_close_callback():
    print("WebSocket connection closed.")
 
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
        pass
except KeyboardInterrupt:
    print("WebSocket connection closed.")
    api.stop_websocket()