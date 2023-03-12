import datetime
import logging
import json
import sys
import nuconfig
import threading
import localisation
import telegram
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
import duckbot
import requests
import worker2 as worker
from apscheduler.schedulers.background import BackgroundScheduler
import adminmenu

try:
    import coloredlogs
except ImportError:
    coloredlogs = None
MARKDOWN = telegram.parsemode.ParseMode.MARKDOWN
LOCK = threading.Lock()


def send_notification():
    cfg = nuconfig.NuConfig
    bot: telegram.Bot = duckbot.factory(cfg)(request=telegram.utils.request.Request(cfg["Telegram"]["con_pool_size"]))
    base: str = cfg["API"]["base"]
    url = base.format(f"payment/users/")
    users: list[dict] = requests.get(url).json()["users"]
    for user in users:
        if last := float(user.get("last_post")):
            now = datetime.datetime.now().timestamp()
            dur = (now - last) / 90
            if dur >= 90:
                # update the last_post
                url = base.format(f"payment/update_last/")
                user_id: str = user.get("telegram_id")
                effective_user = user.get("effective_id")
                data = {"user_id": user_id, "last": 0.0}
                requests.post(url, data=data)
                try:
                    bot.send_message(
                        effective_user, "you can send posts now"
                    )
                except Exception as e:
                    print(e)
                    continue


def notify_subscription():
    cfg = nuconfig.NuConfig
    bot: telegram.Bot = duckbot.factory(cfg)(request=telegram.utils.request.Request(cfg["Telegram"]["con_pool_size"]))
    base: str = cfg["API"]["base"]
    url = base.format(f"payment/users/")
    users: list[dict] = requests.get(url).json()["users"]
    trans = {
        1: "נשאר לך עוד יום אחרון להשתמש בבוט, דבר עם המנהלים בהקדם",
        7: "נשאר לך עוד שבוע להשתמש בבוט, דבר עם המנהלים"}
    for user in users:
        remaining = int(user.get("days_remaning"))
        if remaining in [1, 7]:
            try:
                bot.send_message(
                    user.get("telegram_id"), f"{trans[remaining]}"
                )
            except Exception:
                continue


def main():
    """The core code of the program. Should be run only in the main process!"""
    # Rename the main thread for presentation purposes
    threading.current_thread().name = "Core"
    scheduler = BackgroundScheduler()
    scheduler.add_job(send_notification, trigger="interval", minutes=1)
    scheduler.add_job(notify_subscription, trigger="interval", minutes=60*12)
    """scheduler.add_job(fivemin, trigger="interval", minutes=5)
    scheduler.add_job(tenmin, trigger="interval", minutes=10)
    scheduler.add_job(thirtymin, trigger="interval", minutes=30)
    scheduler.add_job(onehour, trigger="interval", minutes=60)
    scheduler.add_job(onethirty, trigger="interval", minutes=90)
    scheduler.add_job(twohours, trigger="interval", minutes=120)
    scheduler.add_job(threehours, trigger="interval", minutes=180)

    scheduler.start()"""
    scheduler.start()
    # Start logging setup
    log = logging.getLogger("core")
    logging.root.setLevel("INFO")
    log.debug("Set logging level to INFO while the config is being loaded")

    # Ensure the template config file exists
    user_cfg = nuconfig.NuConfig
    # logging.root.setLevel(user_cfg["Logging"]["level"])
    stream_handler = logging.StreamHandler()
    """if coloredlogs is not None:
        stream_handler.formatter = coloredlogs.ColoredFormatter(user_cfg["Logging"]["format"], style="{")
    else:
        stream_handler.formatter = logging.Formatter(user_cfg["Logging"]["format"], style="{")"""
    # stream_handler.formatter = logging.Formatter(user_cfg["Logging"]["format"], style="{")
    logging.root.handlers.clear()
    logging.root.addHandler(stream_handler)
    log.debug("Logging setup successfully!")

    # Ignore most python-telegram-bot logs, as they are useless most of the time
    logging.getLogger("telegram").setLevel("ERROR")

    # Create a bot instance
    bot = duckbot.factory(user_cfg)(request=telegram.utils.request.Request(user_cfg["Telegram"]["con_pool_size"]))

    # Test the specified token
    log.debug("Testing bot token...")
    me = bot.get_me()
    if me is None:
        logging.fatal("The token you have entered in the config file is invalid")
        sys.exit(1)
    log.debug("Bot token is valid!")

    # Finding default language
    default_language = user_cfg["Language"]["default_language"]
    default_loc = localisation.Localisation(default_language)
    # Create a dictionary linking the chat ids to the Worker objects
    # {"1234": <Worker>}
    chat_workers = {}

    # Current update offset; if None it will get the last 100 unparsed messages
    next_update = None

    # Notify on the console that the bot is starting
    log.info(f"@{me.username} is starting!")

    # Main loop of the program
    while True:
        # Get a new batch of 100 updates and mark the last 100 parsed as read
        update_timeout = user_cfg["Telegram"]["long_polling_timeout"]
        updates = bot.get_updates(offset=next_update,
                                  timeout=update_timeout)
        # Parse all the updates
        for update in updates:
            update: telegram.Update
            if update.message is not None:
                # Ensure the message has been sent in a private chat
                if update.message.chat.type != "private":
                    continue
                # If the message is a start command...
                if isinstance(update.message.text, str) and update.message.text.startswith("/start"):
                    log.info(f"Received /start from: {update.message.chat.id}, {update.message.from_user.username}")
                    # Check if a worker already exists for that chat
                    old_worker = chat_workers.get(update.message.chat.id)
                    # If it exists, gracefully stop the worker
                    if old_worker:
                        log.debug(f"Received request to stop {old_worker.name}")
                        old_worker.stop("request")
                    # Initialize a new worker for the chat
                    new_worker = worker.Worker(
                        bot=bot,
                        chat=update.message.chat,
                        telegram_user=update.message.from_user, cfg=user_cfg,
                        daemon=True
                    )
                    new_worker.start()
                    # Store the worker in the dictionary
                    chat_workers[update.message.chat.id] = new_worker
                    # Skip the update
                    continue
                if isinstance(update.message.text, str) and update.message.text.startswith("/id"):
                    update.message.reply_text(
                        f"{update.message.from_user.id}"
                    )
                    continue
                receiving_worker = chat_workers.get(update.message.chat.id)
                # Ensure a worker exists for the chat and is alive
                if receiving_worker is None:
                    bot.send_message(
                        update.message.chat.id,
                        "Press /start to restart the bot"
                    )
                    continue
                if not receiving_worker.is_ready():
                    continue
                # If the message contains the "Cancel" string defined in the strings file...
                if update.message.text == receiving_worker.loc.get("menu_cancel"):
                    receiving_worker.queue.put(worker.CancelSignal())
                else:
                    log.debug(f"Forwarding message to {receiving_worker}")
                    # Forward the update to the worker
                    receiving_worker.queue.put(update)

            # If the update is an inline keyboard press...
            if isinstance(update.callback_query, telegram.CallbackQuery):
                # Forward the update to the corresponding worker
                receiving_worker = chat_workers.get(update.callback_query.from_user.id)
                # Ensure a worker exists for the chat
                if receiving_worker is None:
                    # Suggest that the user restarts the chat with /start
                    bot.send_message(
                        update.callback_query.from_user.id,
                        "Press /start to restart the bot"
                    )
                    continue
                data = update.callback_query.data
                if "delete" in data:
                    update.callback_query.answer()
                    # update.callback_query.message.delete()
                    pk = data.split("_")[1]
                    receiving_worker.delete_post(pk)
                    try:
                        update.callback_query.edit_message_text(receiving_worker.loc.get("post_deleted"))
                    except Exception as e:
                        print(e)
                    continue
                receiving_worker.queue.put(update)

        # If there were any updates...
        if len(updates):
            # Mark them as read by increasing the update_offset
            next_update = updates[-1].update_id + 1


# Run the main function only in the main process
if __name__ == "__main__":
    main()
