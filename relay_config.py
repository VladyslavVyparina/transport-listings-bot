import os

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# Source channel: new posts are copied onward, except the scheduled push.
SOURCE_CHAT_ID = int(os.environ.get("SOURCE_CHAT_ID", "-1002031991424"))

# Destination channel for the relay.
DEST_CHAT_ID = int(os.environ.get("DEST_CHAT_ID", "-1004349240981"))
