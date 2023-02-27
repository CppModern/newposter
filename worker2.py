import datetime
import sys
import logging
import queue as queuem
import threading
import traceback
import json
import requests
import nuconfig
import telegram
import _signals
import localisation
import adminmenu as menu
from telegram import (
    InlineKeyboardMarkup, InlineKeyboardButton
)
from utils import (
    wait_for_photo, wait_for_regex,
    wait_for_inlinekeyboard_callback,
    receive_next_update, wait_for_specific_message,
    graceful_stop, buildmenubutton
)

log = logging.getLogger(__name__)
CancelSignal = _signals.CancelSignal
StopSignal = _signals.StopSignal
MARKDOWN = telegram.parsemode.ParseMode.MARKDOWN


class Worker(threading.Thread):
    CancelSignal = _signals.CancelSignal
    StopSignal = _signals.StopSignal
    wait_for_specific_message = wait_for_specific_message
    wait_for_inlinekeyboard_callback = wait_for_inlinekeyboard_callback
    receive_next_update = receive_next_update
    wait_for_photo = wait_for_photo
    wait_for_regex = wait_for_regex
    graceful_stop = graceful_stop

    admin_group_menu = menu.group_menu
    admin_post_menu = menu.postmenu
    admin_promote_menu = menu.add_admin
    admin_edit_menu = menu.edit_post

    def __init__(
        self,
        bot,
        chat: telegram.Chat,
        telegram_user: telegram.User,
        cfg: nuconfig.NuConfig,
        *args,
        **kwargs,
    ):
        # Initialize the thread
        super().__init__(name=f"Worker {chat.id}", *args, **kwargs)
        # Store the bot, chat info and config inside the class
        self.bot: telegram.Bot = bot
        self.chat: telegram.Chat = chat
        self.todelete = []
        self.telegram_user: telegram.User = telegram_user
        self.cfg = cfg
        self.special = False
        self.admin = False
        # The sending pipe is stored in the Worker class,
        # allowing the forwarding of messages to the chat process
        self.queue = queuem.Queue()
        # The current active invoice payload; reject all invoices
        # with a different payload
        self.invoice_payload = None
        self.loc: localisation.Localisation = None
        self.__create_localization()
        self.cancel_marked = telegram.InlineKeyboardMarkup(
            [[telegram.InlineKeyboardButton(self.loc.get("menu_cancel"), callback_data="cmd_cancel")]])
        self.cancel_list = [telegram.InlineKeyboardButton(self.loc.get("menu_cancel"), callback_data="cmd_cancel")]
        # The price class of this worker.

    def __repr__(self):
        return f"<{self.__class__.__qualname__} {self.chat.id}>"

    def run(self):
        """The conversation code."""
        self.create_user()
        log.debug("Starting conversation")
        # Capture exceptions that occour during the conversation
        # noinspection PyBroadException
        user = self.get_user(self.telegram_user.id)
        try:
            """# Welcome the user to the bot
            if self.cfg["Appearance"]["display_welcome_message"] == "yes":
                self.bot.send_message(
                    self.chat.id, self.loc.get("welcome")
                )
                self.cfg["Appearance"]["display_welcome_message"] = "no"""
            if "expired" in user:
                self.bot.send_message(
                    self.telegram_user.id,
                    self.loc.get("no_perm")
                )
                return
            self.special = user["special"]
            self.admin = user["admin"]
            if self.special or self.admin:
                self.admin_menu()
            else:
                self.bot.send_message(
                    self.chat.id,
                    self.loc.get("no_perm")
                )

        except Exception as e:
            # Try to notify the user of the exception
            # noinspection PyBroadException
            try:
                self.bot.send_message(
                    self.chat.id, self.loc.get("fatal_conversation_exception")
                )
            except Exception as ne:
                log.error(
                    f"Failed to notify the user of a conversation exception: {ne}"
                )
            log.error(f"Exception in {self}: {e}")
            traceback.print_exception(*sys.exc_info())

    def is_ready(self):
        # Change this if more parameters are added!
        return self.loc is not None

    def stop(self, reason: str = ""):
        """Gracefully stop the worker process"""
        # Send a stop message to the thread
        self.queue.put(StopSignal(reason))
        # Wait for the thread to stop
        self.join()

    """def update_user(self):
        user_data = json.loads(
            requests.get(self.cfg["API"]["base"].format(f"payment/user/{self.user.id}")).json()["user"]
        )
        self.user = User(user_data[0], user=self.telegram_user)
        return self.user"""

    def __create_localization(self):
        self.loc = localisation.Localisation("heb")

    def admin_menu(self, selection: telegram.CallbackQuery = None):
        if self.admin:
            data = {
                "add_group": self.loc.get("group_add"),
                "del_group": self.loc.get("group_delete"),
                "view_group": self.loc.get("group_view"),
                "add_admin": self.loc.get("admin_add"),
                "del_admin": self.loc.get("admin_del"),
                "view_admin": self.loc.get("admin_view"),
                "lang": self.loc.get("language_button")
            }
        elif self.special:
            data = {
                #"group": self.loc.get("group_button"),
                "new": self.loc.get("newPost"),
                "pub": self.loc.get("post_send"),
                "hist": self.loc.get("myPost"),
                "edit": "EDIT POST",
                "lang": self.loc.get("language_button")
            }
        buttons = buildmenubutton(data, cancellable=False)
        if self.special:
            buttons.append(
                [telegram.InlineKeyboardButton(
                    self.loc.get("contact",), url="https://t.me/adduserst"
                )]
            )
        text = self.loc.get("welcome") if self.admin else self.loc.get("welcome_user")
        if not selection:
            self.bot.send_message(
                self.chat.id,
                text=text,
                reply_markup=telegram.InlineKeyboardMarkup(
                    buttons
                ),
            )
        else:
            selection.edit_message_text(
                text,
                reply_markup=telegram.InlineKeyboardMarkup(
                    buttons
                ),
                parse_mode=MARKDOWN
            )
        selection = self.wait_for_inlinekeyboard_callback()
        if selection.data in ["pub", "new", "hist"]:
            self.admin_post_menu(selection=selection)
        elif "group" in selection.data:
            self.admin_group_menu(selection=selection)
        elif selection.data == "edit":
            self.admin_edit_menu(selection=selection)
        elif "admin" in selection.data:
            self.admin_promote_menu(selection=selection)
        elif selection.data == "lang":
            self.switch_context(selection=selection)

    def switch_context(self, selection: telegram.CallbackQuery = None):
        if self.loc.code != "en":
            data = {
                "en": "English 🇱🇷"
            }
        else:
            data = {
                "heb": "Hebrew 🇮🇱"
            }
        button = buildmenubutton(data)

        selection.edit_message_text(
            self.loc.get("langPrompt"),
            reply_markup=telegram.InlineKeyboardMarkup(button)
        )
        selection = self.wait_for_inlinekeyboard_callback(cancellable=True)
        if selection.data == "cmd_cancel":
            return self.admin_menu(selection)
        self.loc = localisation.Localisation(selection.data)
        return self.admin_menu(selection)

    def get_orders(self):
        url = self.cfg["API"]["base"].format(f"payment/orders/{self.telegram_user.id}/")
        orders = requests.get(url).json()["orders"]
        return orders

    def list_products(self):
        url = self.cfg["API"]["base"].format("payment/products/")
        prods = requests.get(url).json()["products"]
        return prods

    def get_users(self):
        url = self.cfg["API"]["base"].format("payment/users/")
        users = requests.get(url).json()["users"]
        return users

    def addorder(self, details):
        url = self.cfg["API"]["base"].format("payment/addorder/")
        requests.post(url, details)

    def getorders(self, user_id):
        url = self.cfg["API"]["base"].format(f"payment/orders/{user_id}")
        res = requests.get(url).json()
        return res["orders"]

    def user_dump(self):
        url = self.cfg["API"]["base"].format("payment/usersdump/")
        res = requests.get(url).json()["users"]
        return res

    def create_or_update_product(self, data, update=False):
        if update:
            url = self.cfg["API"]["base"].format("payment/updateproduct/")
        else:
            url = self.cfg["API"]["base"].format("payment/createproduct/")
        res = requests.post(url, data=data).json()
        return res

    def delete_product(self, product):
        url = self.cfg["API"]["base"].format("payment/deleteproduct/")
        res = requests.post(url, data={"product_id": product})
        return res.json()

    def get_banned_users(self):
        url = self.cfg["API"]["base"].format("payment/users/banned/")
        users = json.loads(requests.get(url).json()["users"])
        data = []
        for user in users:
            data.append(user["fields"])
        return data

    def create_user(self):
        url = self.cfg["API"]["base"].format("payment/createuser/")
        data = {
            "user_id": self.telegram_user.id,
            "fname": self.telegram_user.first_name,
            "username": self.telegram_user.username or ""
        }
        requests.post(url, data=data)

    def ban(self, user):
        user = str(user)
        data = {"user_id": user, "loc": self.telegram_user.language_code}
        url = self.cfg["API"]["base"].format(f"payment/ban/")
        res = requests.post(url, data=data).json()
        return res

    def unban(self, user):
        user = str(user)
        data = {"user_id": user, "loc": self.telegram_user.language_code}
        url = self.cfg["API"]["base"].format(f"payment/unban/")
        res = requests.post(url, data=data).json()
        return res

    def update_balace(self, user, amout, charge=False):
        user = str(user)
        if charge:
            data = {"user_id": user, "amount": amout, "charge": True}
        else:
            data = {"user_id": user, "amount": amout}
        url = self.cfg["API"]["base"].format(f"payment/balance/")
        res = requests.post(url, data=data).json()
        return res

    def get_user(self, user_id):
        url = self.cfg["API"]["base"].format(f"payment/user/{user_id}/")
        user = requests.get(url).json()
        if "expired" in user:
            return user
        return user["user"]

    def create_order(self, user, product_id, qty, coupon=None):
        data = {"user": user, "product_id": product_id, "qty": qty, "coupon": coupon}
        url = self.cfg["API"]["base"].format(f"payment/createorder/")
        res = requests.post(url, data=data).json()
        return res

    def pending_user_orders(self, user):
        url = self.cfg["API"]["base"].format(f"payment/pendingorders/{user}")
        res = requests.get(url)
        return res.json()["orders"]

    def settled_user_orders(self, user):
        url = self.cfg["API"]["base"].format(f"payment/settledorders/{user}")
        res = requests.get(url)
        return res.json()["orders"]

    def create_payment(self, user, amount):
        data = {"user_id": user, "amount": amount}
        url = self.cfg["API"]["base"].format(f"payment/create/")
        res = requests.post(url, data=data).json()
        return res

    def get_user_groups(self):
        url = self.cfg["API"]["base"].format(f"payment/groups/{self.telegram_user.id}")
        res = requests.get(url).json()
        return res["groups"]

    def get_groups(self):
        url = self.cfg["API"]["base"].format(f"payment/groups/")
        res = requests.get(url).json()
        return res["groups"]

    def add_group(self, data):
        url = self.cfg["API"]["base"].format(f"payment/addgroup/")
        res = requests.post(url, data=data).json()
        return res

    def delete_group(self, group_id):
        url = self.cfg["API"]["base"].format(f"payment/deletegroup/")
        data = {"group_id": group_id}
        res = requests.post(url, data=data)
        return res.json()

    def permit_group(self, group_id, user_id):
        data = {"group_id": group_id, "user_id": user_id}
        url = self.cfg["API"]["base"].format(f"payment/permit/")
        res = requests.post(url, data=data).json()
        return res

    def add_post(self, data: dict, post_id=None):
        if post_id:
            data["post_id"] = post_id
        url = self.cfg["API"]["base"].format(f"payment/post/")
        res = requests.post(url, data=data).json()
        return res

    def get_user_posts(self):
        url = self.cfg["API"]["base"].format(f"payment/userposts/{self.telegram_user.id}")
        res = requests.get(url).json()
        return res["posts"]

    def delete_post(self, pk):
        url = self.cfg["API"]["base"].format("payment/deletepost/")
        data = {"post_id": pk}
        res = requests.post(url, data=data)
        return res

    def promoteuser(self, user_id, days):
        url = self.cfg["API"]["base"].format("payment/promote/")
        data = {"user_id": user_id, "days": days}
        res = requests.post(url, data=data)
        return res

    def track_payment(self, order_id):
        url = self.cfg["API"]["base"].format(f"payment/invoice/{order_id}")
        res = requests.get(url).json()
        return res["data"]

    def transaction_times(self, day="today"):
        url = self.cfg["API"]["base"].format(f"payment/transaction{day}/")
        res = requests.get(url).json()
        return res["transactions"]

    def send_post(self, posts):
        bot: telegram.Bot = self.bot
        base: str = self.cfg["API"]["base"]
        url = base.format(f"payment/update_last/")
        data = {"user_id": self.telegram_user.id, "last": datetime.datetime.now().timestamp()}
        requests.post(url, data=data)
        """posts = requests.get(url).json()["posts"]"""
        for post in posts:
            media = post["media"]
            text = post["content"]
            button = post["buttons"].strip()
            if button:
                buttons = button.split("<>")
                blist = []
                for each in buttons:
                    each: str
                    each = each.split("|")
                    try:
                        disp, url = each
                        url = url.strip()
                    except ValueError as e:
                        print(f"{each=},  {e}")
                        button = ""
                        continue
                    blist.append(
                        [InlineKeyboardButton(disp, url=url)]
                    )
            groups: str = post["groups"]
            groups = groups.split(" ")
            if not media:
                for group in groups:
                    try:
                        if button:
                            bot.send_message(
                                group,
                                text,
                                reply_markup=InlineKeyboardMarkup(blist)
                            )
                        else:
                            bot.send_message(
                                group,
                                text,
                            )
                    except Exception as e:
                        print(e)
                        continue
            else:
                media_type = post["media_type"]
                for group in groups:
                    try:
                        if not button:
                            if media_type == 0:
                                bot.send_photo(
                                    group,
                                    photo=media,
                                    caption=text,
                                    parse_mode=MARKDOWN
                                )
                            elif media_type == 1:
                                bot.send_video(
                                    group,
                                    video=media,
                                    caption=text,
                                    parse_mode=MARKDOWN
                                )
                            elif media_type == 2:
                                send_animation(
                                    group,
                                    animation=media,
                                    caption=text,
                                    parse_mode=MARKDOWN
                                )
                        else:
                            # Posts with buttons
                            if media_type == 0:
                                bot.send_photo(
                                    group,
                                    photo=media,
                                    caption=text,
                                    reply_markup=InlineKeyboardMarkup(blist),
                                    parse_mode=MARKDOWN
                                )
                            elif media_type == 1:
                                bot.send_video(
                                    group,
                                    video=media,
                                    caption=text,
                                    reply_markup=InlineKeyboardMarkup(blist),
                                    parse_mode=MARKDOWN
                                )
                            elif media_type == 2:
                                send_animation(
                                    group,
                                    animation=media,
                                    caption=text,
                                    reply_markup=InlineKeyboardMarkup(blist),
                                    parse_mode=MARKDOWN
                                )
                    except Exception as e:
                        print(e)
                        continue
