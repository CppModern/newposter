import csv
import json
import os
import tempfile
import threading

import telegram
from telegram import InlineKeyboardMarkup
from telegram import InlineKeyboardButton
from telegram.chatmember import ChatMemberAdministrator
import worker2
from pathlib import Path
import _signals
import utils
from datetime import datetime, timedelta
MARKDOWN = telegram.parsemode.ParseMode.MARKDOWN
CancelSignal = _signals.CancelSignal
StopSignal = _signals.StopSignal
LOCK = threading.Lock()


def group_menu(worker: "worker2.Worker", selection: telegram.CallbackQuery = None):
    add, delete, view = "add_group", "del_group", "view_group"
    if selection.data == add:
        selection.edit_message_text(
            worker.loc.get("group_username"),
            reply_markup=worker.cancel_marked,
            parse_mode=telegram.ParseMode.MARKDOWN
        )
        selection = worker.wait_for_regex("(.+)", cancellable=True)
        if isinstance(selection, telegram.Update):
            return worker.admin_menu(selection=selection.callback_query)
        try:
            if selection.isnumeric() and not selection.startswith("-100"):
                selection = f"-100{selection}"
            admins = worker.bot.getChatAdministrators(selection)
        except telegram.error.BadRequest as e:
            if "not found" in e.message:
                worker.bot.send_message(
                    worker.chat.id,
                    worker.loc.get("group_not_found")
                )
                return worker.admin_menu()
        can_manage = False
        for admin in admins:
            admin: ChatMemberAdministrator
            if admin.user == worker.bot.bot:
                if admin.can_manage_chat:
                    can_manage = True
        if not can_manage:
            # inform the admin to add the  bot to the group
            worker.bot.send_message(
                worker.chat.id,
                worker.loc.get("group_admin_error")
            )
            return worker.admin_menu()
        info = worker.bot.getChat(selection)
        group_id, group_title = info["id"], info["title"]
        owner = worker.telegram_user.id
        data = {"group_id": group_id, "group_title": group_title, "owner": f"{owner}"}
        worker.add_group(data)

        worker.bot.send_message(
            worker.chat.id,
            worker.loc.get("group_add_ok").format(group_title)
        )
        return worker.admin_menu()
    elif selection.data == view:
        groups = worker.get_groups()
        if not groups:
            selection.edit_message_text(
                worker.loc.get("group_not_available"),
                parse_mode=telegram.ParseMode.MARKDOWN
            )
            return worker.admin_menu()
        msg = worker.loc.get("groups_intro")
        found = False
        for group in groups:
            if group["group_id"] in [1234, 5678]:
                continue
            try:
                group_json = worker.bot.getChat(group["group_id"])
            except Exception:
                worker.delete_group(group["group_id"])
                continue
            found = True
            username = group_json["username"]
            link = group_json["invite_link"]
            username = link or f"https://t.me/{username}"
            title = group_json["title"]
            info = f"[{title}]({username}) \n\n"
            msg = msg + info
        if not found:
            selection.edit_message_text(
                worker.loc.get("group_not_available"),
                parse_mode=telegram.ParseMode.MARKDOWN
            )
            return worker.admin_menu()
        selection.edit_message_text(
            msg,
            parse_mode=telegram.ParseMode.MARKDOWN
        )
        return worker.admin_menu()
    elif selection.data == delete:
        groups = worker.get_groups()
        if not groups:
            selection.edit_message_text(
                worker.loc.get("group_not_available"),
                parse_mode=telegram.ParseMode.MARKDOWN
            )
            return worker.admin_menu()

        gdata = {}
        for group in groups:
            gdata[group["group_id"]] = group["group_title"]
        buttons = utils.buildmenubutton(gdata)
        selection.edit_message_text(
            worker.loc.get("group_delete_info"),
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=telegram.ParseMode.MARKDOWN
        )
        selection = worker.wait_for_inlinekeyboard_callback(cancellable=True)
        if selection.data == "cmd_cancel":
            return worker.admin_menu(selection)
        worker.delete_group(selection.data)
        selection.edit_message_text(
            worker.loc.get("group_deleted")
        )
        return worker.admin_menu()


def edit_post(worker: "worker2.Worker", selection: telegram.CallbackQuery = None):
    posts = worker.get_user_posts()
    if not posts:
        selection.edit_message_text(
            worker.loc.get("no_posts")
        )
        return worker.admin_menu()
    selection.edit_message_text(
        worker.loc.get("posts_hist_info")
    )

    groups = worker.get_groups()
    if not groups:
        worker.bot.send_message(
            worker.chat.id,
            worker.loc.get("group_not_available")
        )
        return worker.admin_menu()
    amoutnt = len(posts)
    current = 0
    previous = -1
    hasprev = previous >= 0
    hasnext = (amoutnt - current) > 1
    while True:
        post = posts[current]
        media = post["media"]
        text = post["content"]
        pk = post["pk"]
        data = {}
        if hasprev:
            data["prev"] = "Prev ⏮️"
        data[f"edit_{pk}"] = worker.loc.get("delete_post")
        if hasnext:
            data["next"] = "Next ⏭️"
        butt = utils.buildmenubutton(
            data,
            cancellable=True
        )
        if not media:
            worker.bot.send_message(
                worker.chat.id,
                text,
                reply_markup=InlineKeyboardMarkup(butt)
            )
        else:
            media_type = post["media_type"]
            if media_type == 0:
                worker.bot.send_photo(
                    worker.chat.id,
                    photo=media,
                    caption=text,
                    reply_markup=InlineKeyboardMarkup(butt),
                    parse_mode=MARKDOWN
                )
            elif media_type == 1:
                worker.bot.send_video(
                    worker.chat.id,
                    video=media,
                    caption=text,
                    reply_markup=InlineKeyboardMarkup(butt),
                    parse_mode=MARKDOWN
                )
            elif media_type == 2:
                worker.bot.send_animation(
                    worker.chat.id,
                    animation=media,
                    caption=text,
                    reply_markup=InlineKeyboardMarkup(butt),
                    parse_mode=MARKDOWN
                )
        selection = worker.wait_for_inlinekeyboard_callback(cancellable=True)
        if selection.data == "cmd_cancel":
            return worker.admin_menu()
        elif selection.data == "next":
            previous = current
            hasprev = True
            current += 1
            hasnext = (amoutnt - current) > 1
        elif selection.data == "prev":
            current = previous
            previous -= 1
            hasprev = previous >= 0
            hasnext = True
        else:
            break
    post_id = pk
    worker.bot.send_message(
        worker.chat.id,
        worker.loc.get("post_text"),
        reply_markup=worker.cancel_marked,
    )
    selection = worker.wait_for_regex("(.*)", cancellable=True, mark=True)
    if isinstance(selection, telegram.Update):
        return worker.admin_menu(selection.callback_query)
    text = selection
    gdata = {}
    for group in groups:
        gdata[group["group_id"]] = group["group_title"]
    buttons = utils.buildmenubutton(gdata)
    buttons.append([InlineKeyboardButton(worker.loc.get("menu_done"), callback_data="cmd_done")])
    buttons_copy = list(buttons)
    worker.bot.send_message(
        worker.chat.id,
        worker.loc.get("post_groups"),
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    selected = 0
    while True:
        selection = worker.wait_for_inlinekeyboard_callback(cancellable=True)
        if selection.data == "cmd_cancel":
            return worker.admin_post_menu(selection=selection)
        elif selection.data == "cmd_done":
            # check at least one user selected for the pm
            if not selected:
                continue
            else:
                break
        for kb in buttons_copy:
            for k in kb:
                if k.callback_data == selection.data:
                    if "✅" in k.text:
                        k.text = k.text.replace("✅", "")
                        selected -= 1
                    else:
                        k.text = k.text + " ✅"
                        selected += 1
        selection.edit_message_text(
            worker.loc.get("post_groups"),
            reply_markup=InlineKeyboardMarkup(buttons_copy)
        )
    ids = []
    for kb in buttons_copy:
        for k in kb:
            if "✅" in k.text and (k.callback_data != "cmd_done"):
                ids.append(k.callback_data)
    groups = " ".join(ids)
    groups = groups.strip()
    buttons = utils.buildmenubutton({}, skip=True)
    selection.edit_message_text(
        worker.loc.get("post_media"),
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    selection = worker.wait_for_photo(cancellable=True)
    data = selection
    has_media = False
    if isinstance(data, telegram.Update):
        if data.callback_query.data == "cmd_cancel":
            return worker.admin_menu(selection.callback_query)
    else:
        has_media = True
        if isinstance(data, list):
            first: telegram.PhotoSize = data[0]
            media = first.file_id
            media_type = 0
        elif isinstance(data, telegram.Video):
            media = data.file_id
            media_type = 1
        elif isinstance(data, telegram.Animation):
            media = data.file_id
            media_type = 2
    hasbutt = True
    blist = [[InlineKeyboardButton("😎פנה למפרסם😎", url=f"https://t.me/{worker.telegram_user.username}")]]
    log = worker.bot.send_message(
        worker.chat.id,
        worker.loc.get("confirm_info")
    )
    try:
        if not has_media:
            if not hasbutt:
                msg = worker.bot.send_message(
                    worker.chat.id,
                    text
                )
            else:
                msg = worker.bot.send_message(
                    worker.chat.id,
                    text,
                    reply_markup=InlineKeyboardMarkup(blist)
                )
        else:
            if hasbutt:
                if media_type == 0:
                    msg = worker.bot.send_photo(
                        worker.chat.id,
                        photo=media,
                        caption=text,
                        reply_markup=InlineKeyboardMarkup(blist),
                        parse_mode=MARKDOWN
                    )
                elif media_type == 1:
                    msg = worker.bot.send_video(
                        worker.chat.id,
                        video=media,
                        caption=text,
                        reply_markup=InlineKeyboardMarkup(blist),
                        parse_mode=MARKDOWN
                    )
                elif media_type == 2:
                    msg = worker.bot.send_animation(
                        worker.chat.id,
                        animation=media,
                        caption=text,
                        reply_markup=InlineKeyboardMarkup(blist),
                        parse_mode=MARKDOWN
                    )
            else:
                if media_type == 0:
                    msg = worker.bot.send_photo(
                        worker.chat.id,
                        photo=media,
                        caption=text,
                        parse_mode=MARKDOWN
                    )
                elif media_type == 1:
                    msg = worker.bot.send_video(
                        worker.chat.id,
                        video=media,
                        caption=text,
                        parse_mode=MARKDOWN
                    )
                elif media_type == 2:
                    msg = worker.bot.send_animation(
                        worker.chat.id,
                        animation=media,
                        caption=text,
                        parse_mode=MARKDOWN
                    )
    except Exception as e:
        print(e)
        worker.bot.send_message(
            worker.chat.id,
            worker.loc.get("critical")
        )
        return worker.admin_menu()
    confirm = {"confirm": worker.loc.get("confirm")}
    confirmbut = utils.buildmenubutton(confirm)
    worker.bot.send_message(
        worker.chat.id,
        worker.loc.get("confirm_prompt"),
        reply_markup=InlineKeyboardMarkup(confirmbut)
    )
    selection = worker.wait_for_inlinekeyboard_callback(cancellable=True)
    if selection.data == "cmd_cancel":
        log.delete()
        msg.delete()
        return worker.admin_menu(selection)
    data = {"content": text, "user_id": worker.telegram_user.id, "duration": "", "groups": groups}
    if has_media:
        data["media"] = media
        data["media_type"] = media_type
    if hasbutt:
        data["button"] = f"😎פנה למפרסם😎 | https://t.me{worker.telegram_user.username}"
    log.delete()
    msg.delete()
    worker.add_post(data, post_id=post_id)
    selection.edit_message_text(
        worker.loc.get("post_add_ok"),
    )
    return worker.admin_menu()


def postmenu(worker: "worker2.Worker", selection: telegram.CallbackQuery = None):
    if selection.data == "new":
        groups = worker.get_groups()
        if not groups:
            if selection:
                selection.edit_message_text(
                    worker.loc.get("group_not_available")
                )
                return worker.admin_menu()
            worker.bot.send_message(
                worker.chat.id,
                worker.loc.get("group_not_available")
            )
            return worker.admin_menu()
        selection.edit_message_text(
            worker.loc.get("post_text"),
            reply_markup=worker.cancel_marked,
            parse_mode=MARKDOWN
        )
        selection = worker.wait_for_regex("(.*)", cancellable=True, mark=True)
        if isinstance(selection, telegram.Update):
            return worker.admin_menu(selection.callback_query)
        text = selection
        gdata = {}
        for group in groups:
            gdata[group["group_id"]] = group["group_title"]
        buttons = utils.buildmenubutton(gdata)
        buttons.append([InlineKeyboardButton(worker.loc.get("menu_done"), callback_data="cmd_done")])
        buttons_copy = list(buttons)
        worker.bot.send_message(
            worker.chat.id,
            worker.loc.get("post_groups"),
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        selected = 0
        while True:
            selection = worker.wait_for_inlinekeyboard_callback(cancellable=True)
            if selection.data == "cmd_cancel":
                return worker.admin_post_menu(selection=selection)
            elif selection.data == "cmd_done":
                # check at least one user selected for the pm
                if not selected:
                    continue
                else:
                    break
            for kb in buttons_copy:
                for k in kb:
                    if k.callback_data == selection.data:
                        if "✅" in k.text:
                            k.text = k.text.replace("✅", "")
                            selected -= 1
                        else:
                            k.text = k.text + " ✅"
                            selected += 1
            selection.edit_message_text(
                worker.loc.get("post_groups"),
                reply_markup=InlineKeyboardMarkup(buttons_copy)
            )
        ids = []
        for kb in buttons_copy:
            for k in kb:
                if "✅" in k.text and (k.callback_data != "cmd_done"):
                    ids.append(k.callback_data)
        groups = " ".join(ids)
        groups = groups.strip()
        buttons = utils.buildmenubutton({}, skip=True)
        selection.edit_message_text(
            worker.loc.get("post_media"),
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        selection = worker.wait_for_photo(cancellable=True)
        data = selection
        has_media = False
        if isinstance(data, telegram.Update):
            if data.callback_query.data == "cmd_cancel":
                return worker.admin_menu(selection.callback_query)
        else:
            has_media = True
            if isinstance(data, list):
                first: telegram.PhotoSize = data[0]
                media = first.file_id
                media_type = 0
            elif isinstance(data, telegram.Video):
                media = data.file_id
                media_type = 1
            elif isinstance(data, telegram.Animation):
                media = data.file_id
                media_type = 2
        hasbutt = True
        blist = [[InlineKeyboardButton("😎פנה למפרסם😎", url=f"https://t.me/{worker.telegram_user.username}")]]
        log = worker.bot.send_message(
            worker.chat.id,
            worker.loc.get("confirm_info")
        )
        try:
            if not has_media:
                if not hasbutt:
                    msg = worker.bot.send_message(
                            worker.chat.id,
                            text
                    )
                else:
                    msg = worker.bot.send_message(
                        worker.chat.id,
                        text,
                        reply_markup=InlineKeyboardMarkup(blist)
                    )
            else:
                if hasbutt:
                    if media_type == 0:
                        msg = worker.bot.send_photo(
                            worker.chat.id,
                            photo=media,
                            caption=text,
                            reply_markup=InlineKeyboardMarkup(blist),
                            parse_mode=MARKDOWN
                        )
                    elif media_type == 1:
                        msg = worker.bot.send_video(
                            worker.chat.id,
                            video=media,
                            caption=text,
                            reply_markup=InlineKeyboardMarkup(blist),
                            parse_mode=MARKDOWN
                        )
                    elif media_type == 2:
                        msg = worker.bot.send_animation(
                            worker.chat.id,
                            animation=media,
                            caption=text,
                            reply_markup=InlineKeyboardMarkup(blist),
                            parse_mode=MARKDOWN
                        )
                else:
                    if media_type == 0:
                        msg = worker.bot.send_photo(
                            worker.chat.id,
                            photo=media,
                            caption=text,
                            parse_mode=MARKDOWN
                        )
                    elif media_type == 1:
                        msg = worker.bot.send_video(
                            worker.chat.id,
                            video=media,
                            caption=text,
                            parse_mode=MARKDOWN
                        )
                    elif media_type == 2:
                        msg = worker.bot.send_animation(
                            worker.chat.id,
                            animation=media,
                            caption=text,
                            parse_mode=MARKDOWN
                        )
        except Exception as e:
            print(e)
            worker.bot.send_message(
                worker.chat.id,
                worker.loc.get("critical")
            )
            return worker.admin_menu()
        confirm = {"confirm": worker.loc.get("confirm")}
        confirmbut = utils.buildmenubutton(confirm)
        worker.bot.send_message(
            worker.chat.id,
            worker.loc.get("confirm_prompt"),
            reply_markup=InlineKeyboardMarkup(confirmbut)
        )
        selection = worker.wait_for_inlinekeyboard_callback(cancellable=True)
        if selection.data == "cmd_cancel":
            log.delete()
            msg.delete()
            return worker.admin_menu(selection)
        data = {"content": text, "user_id": worker.telegram_user.id, "groups": groups}
        if has_media:
            data["media"] = media
            data["media_type"] = media_type
        if hasbutt:
            data["button"] = f"😎פנה למפרסם😎 | https://t.me/{worker.telegram_user.username}"
        log.delete()
        msg.delete()
        worker.add_post(data)
        selection.edit_message_text(
            worker.loc.get("post_add_ok"),
        )
        return worker.admin_menu()
    elif selection.data == "pub":
        posts = worker.get_user_posts()
        if not posts:
            worker.bot.send_message(
                worker.chat.id, worker.loc.get("no_posts")
            )
            return
        user = worker.get_user(worker.telegram_user.id)
        last = user["last_post"]
        if not last:
            ...
        else:
            now = datetime.now().timestamp()
            res = (now - last) / 60
            if res < 60:
                worker.bot.send_message(
                    worker.chat.id,
                    worker.loc.get("post_wait").format(int(60 - res))
                )
                return worker.admin_menu()
        worker.send_post(posts)
        worker.bot.send_message(
            worker.chat.id,
            worker.loc.get("post_sent")
        )
        return worker.admin_menu()
    elif selection.data == "hist":
        posts = worker.get_user_posts()
        if not posts:
            selection.edit_message_text(
                worker.loc.get("no_posts")
            )
            return worker.admin_menu()
        selection.edit_message_text(
            worker.loc.get("posts_hist_info")
        )
        for post in posts:
            media = post["media"]
            text = post["content"]
            pk = post["pk"]
            if not media:
                worker.bot.send_message(
                    worker.chat.id,
                    text,
                )
            else:
                media_type = post["media_type"]
                if media_type == 0:
                    worker.bot.send_photo(
                        worker.chat.id,
                        photo=media,
                        caption=text,
                        parse_mode=MARKDOWN
                    )
                elif media_type == 1:
                    worker.bot.send_video(
                        worker.chat.id,
                        video=media,
                        caption=text,
                        parse_mode=MARKDOWN
                    )
                elif media_type == 2:
                    worker.bot.send_animation(
                        worker.chat.id,
                        animation=media,
                        caption=text,
                        parse_mode=MARKDOWN
                    )
        return worker.admin_menu()


def add_admin(worker: "worker2.Worker", selection: telegram.CallbackQuery = None):
    action = selection.data
    if action == "add_admin":
        selection.edit_message_text(
            worker.loc.get("admin_id_promt"),
            reply_markup=worker.cancel_marked
        )
        selection = worker.wait_for_regex("(\d+ \d+)", cancellable=True)
        if isinstance(selection, telegram.Update):
            return worker.admin_menu(selection.callback_query)
        data = selection.split(" ")
        if not data[0].isnumeric():
            worker.bot.send_message(
                worker.chat.id,
                worker.loc.get("admin_id_invalid")
            )
            return worker.admin_menu()
        if (len(data) < 2) or not data[1].isnumeric():
            worker.bot.send_message(
                worker.chat.id,
                worker.loc.get("admin_data_invalid")
            )
            return worker.admin_menu()
        worker.promoteuser(data[0], days=int(data[1]))
        worker.bot.send_message(
            worker.chat.id,
            worker.loc.get("admin_added")
        )
        return worker.admin_menu()
    if action == "view_admin":
        users = worker.get_users()
        if not users:
            worker.bot.send_message(
                worker.chat.id,
                worker.loc.get("admin_unavailable")
            )
            return worker.admin_menu()
        text = f"{worker.loc.get('admin_available')}\n\n\n"
        fmt = "User ID: {telegram_id}\nDate Permitted: {date_added}\nExpiry Date: {expiry}\n"\
              "Day Remaning: {days_remaning}\n\n\n"
        for user in users:
            text += fmt.format(**user)
        worker.bot.send_message(
            worker.chat.id,
            text
        )
        return worker.admin_menu()
    else:
        selection.edit_message_text(
            worker.loc.get("admin_id_delete"),
            reply_markup=worker.cancel_marked
        )
        selection = worker.wait_for_regex("(\d+)", cancellable=True)
        if isinstance(selection, telegram.Update):
            return worker.admin_menu(selection.callback_query)
        res = worker.ban(selection)
        if "error" in res:
            worker.bot.send_message(
                worker.chat.id,
                worker.loc.get("admin_invalid")
            )
            return worker.admin_menu()
        worker.bot.send_message(
            worker.chat.id,
            worker.loc.get("admin_deleted")
        )
    return worker.admin_menu()
