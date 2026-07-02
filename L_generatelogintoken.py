import subprocess
import time
import sys

# Run first script and wait for it to complete
subprocess.run([sys.executable, "L_getauthcode.py"], check=True)

# Wait 1 second
time.sleep(1)

# Run second script
subprocess.run([sys.executable, "L_newshoonya.py"], check=True)

print("Both scripts completed.")