import subprocess
import sys
import time
from pathlib import Path
import shutil
import yaml
import pandas as pd
from datetime import datetime, timedelta

import A_download_todays_data as dta
# import A_process_buy_sell as pbs
#=======================================================
# Delete all files/folders inside "nifty100_data_today"
folder = Path("nifty100_data_today")

if folder.exists():
    for item in folder.iterdir():
        if item.is_file():
            item.unlink()
        elif item.is_dir():
            shutil.rmtree(item)
    print("Cleared nifty100_data_today folder.")
else:
    folder.mkdir(parents=True)
    print("Created nifty100_data_today folder.")

time.sleep(10)  # Wait for 10 seconds to ensure the folder is created
#======================================================
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
INTERVAL = 5 * 60  # 5 minutes

while True:
    now = datetime.now()
    current_minutes = now.hour * 60 + now.minute

    # Trading window: 09:15 to 15:30
    start_minutes = 9 * 60 + 15
    end_minutes = 15 * 60 + 10
    if start_minutes <= current_minutes <= end_minutes:
        loop_start = time.time()
        
        try:
            # dowload all stocks data
            dta.download_all_stocks(api)

        except subprocess.CalledProcessError as e:
            print(f"Script failed: {e}")

        try:
            # dowload all stocks data
            pbs.process_buy_sell(api)

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