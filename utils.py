import json
import logging
import queue as queuem
import re
import sqlite3
import sys
from typing import *
import telegram
import _signals
from telegram import InlineKeyboardButton
from collections import defaultdict

StopSignal = _signals.StopSignal
CancelSignal = _signals.CancelSignal

log = logging.getLogger(__name__)


def receive_next_update(worker) -> telegram.Update:
    """Get the next update from the queue.
    If no update is found, block the process until one is received.
    If a stop signal is sent, try to gracefully stop the thread."""
    # Pop data from the queue
    try:
        data = worker.queue.get(timeout=worker.cfg["Telegram"]["conversation_timeout"])
    except queuem.Empty:
        # If the conversation times out, gracefully stop the thread
        worker.graceful_stop(StopSignal("timeout"))
    # Check if the data is a stop signal instance
    if isinstance(data, StopSignal):
        # Gracefully stop the process
        worker.graceful_stop(data)
    # Return the received update
    return data


def wait_for_specific_message(
        worker, items: List[str], cancellable: bool = False
) -> Union[str, CancelSignal]:
    """Continue getting updates until one of the strings contained in the list is received as a message."""
    log.debug("Waiting for a specific message...")
    while True:
        # Get the next update
        update = worker.receive_next_update()
        # If a CancelSignal is received...
        if isinstance(update, CancelSignal):
            # And the wait is cancellable...
            if cancellable:
                # Return the CancelSignal
                return update
            else:
                # Ignore the signal
                continue
        # Ensure the update contains a message
        if update.message is None:
            continue
        # Ensure the message contains text
        if update.message.text is None:
            continue
        # Check if the message is contained in the list
        if update.message.text not in items:
            continue
        # Return the message text
        return update.message.text


def wait_for_regex(
        worker, regex: str, cancellable: bool = False, info=None, mark=False
) -> Union[str, CancelSignal]:
    """Continue getting updates until the regex finds a match in a message, then return the first capture group."""
    log.debug("Waiting for a regex...")
    while True:
        # Get the next update
        update: telegram.Update = worker.receive_next_update()
        # If a CancelSignal is received...
        if update.callback_query:
            # And the wait is cancellable...
            if cancellable:
                # Return the CancelSignal
                update.callback_query.answer()
                return update
            else:
                # Ignore the signal
                continue
        # Ensure the update contains a message
        if not update.message:
            continue

        # Ensure the message contains text
        if not update.message.text:
            continue
        # Try to match the regex with the received message
        match = re.search(regex, update.message.text, re.DOTALL)
        # Ensure there is a match
        if match is None:
            if info:
                worker.bot.send_message(
                    worker.chat.id,
                    info
                )
            continue
        # Return the first capture group
        if mark:
            return update.message.text_markdown
        return match.group(1)


def wait_for_precheckoutquery(
        worker, cancellable: bool = False
) -> Union[telegram.PreCheckoutQuery, CancelSignal]:
    """Continue getting updates until a precheckoutquery is received.
    The payload is checked by the core before forwarding the message."""
    log.debug("Waiting for a PreCheckoutQuery...")
    while True:
        # Get the next update
        update = worker.receive_next_update()
        # If a CancelSignal is received...
        if isinstance(update, CancelSignal):
            # And the wait is cancellable...
            if cancellable:
                # Return the CancelSignal
                return update
            else:
                # Ignore the signal
                continue
        # Ensure the update contains a precheckoutquery
        if update.pre_checkout_query is None:
            continue
        # Return the precheckoutquery
        return update.pre_checkout_query


def wait_for_successfulpayment(
        worker, cancellable: bool = False
) -> Union[telegram.SuccessfulPayment, CancelSignal]:
    """Continue getting updates until a successfulpayment is received."""
    log.debug("Waiting for a SuccessfulPayment...")
    while True:
        # Get the next update
        update = worker.receive_next_update()
        # If a CancelSignal is received...
        if isinstance(update, CancelSignal):
            # And the wait is cancellable...
            if cancellable:
                # Return the CancelSignal
                return update
            else:
                # Ignore the signal
                continue
        # Ensure the update contains a message
        if update.message is None:
            continue
        # Ensure the message is a successfulpayment
        if update.message.successful_payment is None:
            continue
        # Return the successfulpayment
        return update.message.successful_payment


def wait_for_photo(
        worker, cancellable: bool = False
):
    """Continue getting updates until a photo is received, then return it."""
    log.debug("Waiting for a photo...")
    while True:
        # Get the next update
        update: telegram.Update = worker.receive_next_update()
        # If a CancelSignal is received...
        if update.callback_query:
            # And the wait is cancellable...
            if update.callback_query.data == "cmd_cancel" and cancellable:
                # Return the CancelSignal
                return update
            elif update.callback_query.data == "cmd_skip":
                return update
            continue
        # Ensure the update contains a message
        if update.message is None:
            continue
        # Ensure the message contains a photo
        if update.message.photo:
            return update.message.photo
        if update.message.animation:
            return update.message.animation
        # Return the photo array
        if update.message.video:
            return update.message.video


def wait_for_inlinekeyboard_callback(
        worker, cancellable: bool = False
) -> Union[telegram.CallbackQuery, CancelSignal]:
    """Continue getting updates until an inline keyboard callback is received, then return it."""
    log.debug("Waiting for a CallbackQuery...")
    while True:
        # Get the next update
        update: telegram.Update = worker.receive_next_update()
        # If a CancelSignal is received...
        if update.callback_query and (update.callback_query.data == "cmd_cancel") and cancellable:
            # And the wait is cancellable...
            update.callback_query.answer()
            return update.callback_query
        if update.callback_query and (update.callback_query.data == "skip") and cancellable:
            update.callback_query.answer()
            return update.callback_query
        if update.callback_query and (update.callback_query.data == "cmd_done") and cancellable:
            update.callback_query.answer()
            return update.callback_query
        # Ensure the update is a CallbackQuery
        if update.callback_query is None:
            continue
        # Answer the callbackquery
        worker.bot.answer_callback_query(update.callback_query.id)
        # Return the callbackquery
        return update.callback_query


def graceful_stop(worker, stop_trigger: StopSignal, msg="conversation_expired", group=None):
    """Handle the graceful stop of the thread."""
    log.debug("Gracefully stopping the conversation")
    # If the session has expired...
    if stop_trigger.reason == "timeout":
        # Notify the user that the session has expired and remove the keyboard
        worker.bot.send_message(
            worker.chat.id,
            worker.loc.get(msg),
            reply_markup=telegram.ReplyKeyboardRemove(),
        )
    elif group:
        msg = worker.loc.get("conversation_not_permited").format(group)
        worker.bot.send_message(
            worker.chat.id,
            msg
        )
    sys.exit(0)


def get_product_data(prods: List[dict]):
    data = {}
    keyboard = []
    inner = []
    data = {prod["product_id"]: prod["title"] for prod in prods}
    return buildmenubutton(data)


def get_users_data(prods: List[dict], exclude=None):
    data = {}
    keyboard = []
    inner = []
    if len(prods) == 1:
        prod = prods[0]
        u = prod["telegram_id"]
        if exclude and (u == str(exclude)):
            return data, keyboard
        data[u] = prod
        username = prod.get("username", prod.get("fname"))
        inner.append(
            InlineKeyboardButton(username, callback_data=prod["telegram_id"])
        )
        keyboard.append(inner)
    else:
        for prod in range(0, len(prods), 2):
            pl = prods[prod: prod + 2]
            for pr in pl:
                u = pr["telegram_id"]
                if exclude and (u == str(exclude)):
                    continue
                data[u] = pr
                username = pr["username"] or pr["fname"]
                if len(username) > 7:
                    user = username[:5] + ".."
                else:
                    user = username
                butt = [
                    InlineKeyboardButton(user, callback_data=pr["telegram_id"])
                ]
                inner.extend(butt)
            keyboard.append(inner)
            inner = []
    return data, keyboard


def get_coupons_data(prods: List[dict]):
    data = {}
    keyboard = []
    inner = []
    if len(prods) == 1:
        prod = prods[0]
        u = prod["code"]
        data[u] = prod
        inner.append(
            InlineKeyboardButton(prod.get("code"), callback_data=prod["code"])
        )
        keyboard.append(inner)
    else:
        for prod in range(0, len(prods), 2):
            pl = prods[prod: prod + 2]
            for pr in pl:
                u = pr["code"]
                if exclude and (u == str(exclude)):
                    continue
                data[u] = pr
                butt = [
                    InlineKeyboardButton(pr.get("code"), callback_data=pr["code"])
                ]
                inner.extend(butt)
            keyboard.append(inner)
            inner = []
    return data, keyboard


def buildmenubutton(data: dict, cancellable=True, skip=False):
    buttons = []
    keys = list(data.keys())
    for i in range(0, len(keys), 2):
        sub = keys[i: i+2]
        info = []
        for j in sub:
            but = InlineKeyboardButton(data.get(j), callback_data=j)
            info.append(but)
        buttons.append(info)
    if cancellable and skip:
        extra = [
            InlineKeyboardButton("🔙 Cancel", callback_data="cmd_cancel"),
            InlineKeyboardButton("⏭ Skip", callback_data="cmd_skip")
        ]
        buttons.append(extra)
    elif cancellable:
        extra = [
            InlineKeyboardButton("🔙 Cancel", callback_data="cmd_cancel"),
        ]
        buttons.append(extra)
    return buttons


def getServiceCategories(key):
    db = sqlite3.connect("services.db", check_same_thread=False)
    cursor = db.cursor()
    query = "select distinct category from panelbotter"
    cursor.execute(query)
    res = cursor.fetchall()
    res = [i[0] for i in res if key in i[0].lower()]
    return res


def getServiceCategoriesStone(key):
    db = sqlite3.connect("services.db", check_same_thread=False)
    cursor = db.cursor()
    query = "select distinct category from telegramadd"
    cursor.execute(query)
    res = cursor.fetchall()
    res = [i[0] for i in res if key in i[0].lower()]
    return res


def serviceCategoryData(category):
    db = sqlite3.connect("services.db", check_same_thread=False)
    cursor = db.cursor()
    cursor2 = db.cursor()
    query = "select * from crescitaly where category = ?"
    query2 = "select * from panelbotter where category = ?"
    cursor.execute(query, (category, ))
    cursor2.execute(query2, (category, ))
    res = cursor.fetchall()
    res2 = cursor2.fetchall()
    keys = ["category", "name", "min", "max", "rate", "service"]
    data = []
    data2 = []
    for i in res:
        info = dict(zip(keys, i))
        data.append(info)
    for i in res2:
        info = dict(zip(keys, i))
        data2.append(info)
    return data2, data


def serviceCategoryDataStone(category):
    db = sqlite3.connect("services.db", check_same_thread=False)
    cursor = db.cursor()
    cursor2 = db.cursor()
    query = "select * from stoneservices where category = ?"
    query2 = "select * from telegramadd where category = ?"
    cursor.execute(query, (category, ))
    cursor2.execute(query2, (category, ))
    res = cursor.fetchall()
    res2 = cursor2.fetchall()
    keys = ["category", "name", "min", "max", "rate", "service"]
    data = []
    data2 = []
    for i in res:
        info = dict(zip(keys, i))
        data.append(info)
    for i in res2:
        info = dict(zip(keys, i))
        data2.append(info)
    return data2, data
