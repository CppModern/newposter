import datetime
from datetime import timedelta
import os
from pathlib import Path
from functools import cache
import django.db.models
import django.http as http
import telegram
from django.http.response import JsonResponse
from django.shortcuts import render, reverse
from django.http import HttpResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from accounts.models import MyUser
from django.core.serializers import serialize
from .models import Product
from .models import Transaction
from .models import Order
from .models import TelegramGroup
from .models import Post
from .models import GroupPermitted

import requests
import uuid
import toml

BASE_DIR = Path(__file__).resolve().parent.parent


def home(request):
    products = Product.objects.all()
    return render(request, "product.html", context={"products": products})


@csrf_exempt
def add_order(request: http.HttpRequest):
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"})
    product_id = request.POST.get("product_id")
    user_id = request.POST.get("user_id")
    user = MyUser.objects.get(telegram_id=user_id)
    product = Product.objects.get(product_id=product_id)
    quantity = product.volume
    order = Order.objects.create(user=user, product=product, quantity=quantity)
    user.balance -= product.price
    order.save()
    user.slots += product.volume
    user.save()
    return JsonResponse({"msg": "OK"})


def get_orders(request: http.HttpRequest, user_id):
    if request.method != "GET":
        return JsonResponse({"error": "method not allowed"})

    user: MyUser = MyUser.objects.get(telegram_id=user_id)
    orders: list[Order] = user.orders.all()
    if not orders:
        return JsonResponse({"orders": []})
    data = []
    for order in orders:
        info = {
            "volume": order.quantity,
            "title": order.product.title,
            "date": order.date.strftime("%D"),
            "description": order.product.description,
            "price": order.product.price
        }
        data.append(info)
    return JsonResponse({"orders": data})


@csrf_exempt
def permit_group(request: http.HttpRequest):
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"})
    group_id = request.POST.get("group_id")
    user = request.POST.get("user_id")
    user = MyUser.objects.get(telegram_id=user)
    group = TelegramGroup.objects.get(group_id=group_id)
    perm: GroupPermitted = GroupPermitted.objects.get_or_create(user=user)[0]
    perm.group.add(group)
    perm.save()
    return JsonResponse({"msg": "OK"})

# ---------------- Post Views


@csrf_exempt
def add_post(request: http.HttpRequest):
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"})
    owner = request.POST.get("user_id")
    post_id = request.POST.get("post_id")
    user = MyUser.objects.get(telegram_id=owner)
    content = request.POST.get("content")
    media = request.POST.get("media") or ""
    buttons = request.POST.get("button") or ""
    groups = request.POST.get("groups")
    if media:
        media_type = request.POST.get("media_type")
    if post_id:
        post: Post = Post.objects.get(pk=post_id)

    else:
        post: Post = Post.objects.create(
            owner=user, content=content, media=media,
            #  media_type=media_type, buttons=buttons, duration=duration, groups=groups
        )
    post.content = content
    post.media = media
    post.buttons = buttons
    post.groups = groups
    if media_type:
        post.media_type = media_type
    post.save()
    return JsonResponse({"msg": "OK"})


def get_posts(request: http.HttpRequest, duration):
    if request.method != "GET":
        return JsonResponse({"error": "method not allowed"})
    posts: list[Post] = Post.objects.filter(duration=duration)
    attrs = ["content", "media", "media_type", "duration", "buttons", "groups"]
    data = []
    for post in posts:
        info = {attr: getattr(post, attr) for attr in attrs}
        data.append(info)
    return JsonResponse({"posts": data})


def get_post(request: http.HttpRequest, post_id):
    if request.method != "GET":
        return JsonResponse({"error": "method not allowed"})
    post = Post.objects.get(pk=post_id)
    attrs = ["content", "media", "media_type", "duration", "buttons", "groups"]
    data = []
    info = {attr: getattr(post, attr) for attr in attrs}
    data.append(info)
    return JsonResponse({"post": data})


@csrf_exempt
def delete_posts(request: http.HttpRequest):
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"})
    pk = request.POST.get("post_id")
    try:
        post: Post = Post.objects.get(pk=pk)
        post.delete()
    except Exception:
        return JsonResponse({"error": "Post not exist"})
    return JsonResponse({"msg": "OK"})


def getuser_posts(request: http.HttpRequest, user_id):
    if request.method != "GET":
        return JsonResponse({"error": "method not allowed"})
    try:
        user: MyUser = MyUser.objects.get(telegram_id=user_id)
    except Exception:
        return JsonResponse({"posts": []})
    posts: list[Post] = user.posts.all()
    attrs = ["content", "media", "media_type", "duration", "buttons", "groups", "pk"]
    data = []
    for post in posts:
        info = {attr: getattr(post, attr) for attr in attrs}
        data.append(info)
    return JsonResponse({"posts": data})
# =====================  TelegramGroup views


@csrf_exempt
def add_group(request: http.HttpRequest):
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"})
    group_id = request.POST.get("group_id")
    group_title = request.POST.get("group_title")
    owner = request.POST.get("owner")
    try:
        group: TelegramGroup = TelegramGroup.objects.create(
            group_title=group_title, group_id=group_id, owner=owner
        )
    except Exception as e:
        print(f"Error in adding group: {e}")
        return JsonResponse({"error": f"{e}"})
    group.save()
    return JsonResponse({"success": "Group add OK"})


def get_groups(request: http.HttpRequest):
    if request.method != "GET":
        return JsonResponse({"error": "method not allowed"})
    groups: list[TelegramGroup] = TelegramGroup.objects.all()
    data = []
    attrs = ["group_id", "group_title"]
    for group in groups:
        info = {attr: getattr(group, attr) for attr in attrs}
        data.append(info)
    return JsonResponse({"groups": data})


@csrf_exempt
def delete_group(request: http.HttpRequest):
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"})
    group_id = request.POST.get("group_id")
    try:
        group: TelegramGroup = TelegramGroup.objects.get(group_id=group_id)
    except Exception:
        return JsonResponse({"error": "No such group"})
    group.delete()
    return JsonResponse({"success": "group deleted"})


def get_user_groups(request: http.HttpRequest, user_id):
    if request.method != "GET":
        return JsonResponse({"error": "method not allowed"})
    attrs = ["group_id", "group_title"]
    groups: list[TelegramGroup] = TelegramGroup.objects.filter(
        owner=user_id
    )
    data = []
    found = set()
    for group in groups:
        if group.group_id in found:
            continue
        info = {attr: getattr(group, attr) for attr in attrs}
        data.append(info)
    return JsonResponse({"groups": data})
# ----------------------- User Views -----------------------------


def get_users(request: http.HttpRequest):
    data = []
    users = MyUser.objects.filter(banned=False, is_admin=False).select_related()
    fields = ["telegram_id", "balance", "period", "last_post", "effective_id"]
    for user in users:
        user: MyUser
        stamp = getattr(user, "period")
        period = datetime.datetime.fromtimestamp(stamp)
        expiry = period - datetime.datetime.now()
        if expiry.days < 0:
            continue
        info = {}
        for field in fields:
            if field == "period":
                info["expiry"] = period.strftime("%D  %H:%M:%S")
                date_added = getattr(user, "date_added")
                info["date_added"] = date_added.strftime("%D  %H:%M:%S")
                info["days_remaning"] = expiry.days
                continue
            info[field] = getattr(user, field)
        data.append(info)
    return JsonResponse({"users": data})


def get_banned_users(request: http.HttpRequest):
    users = serialize(
        "json", MyUser.objects.filter(banned=True),
        fields=["telegram_id", "balance", "status", "fname"]
    )
    return JsonResponse({"users": users})


def get_user(request: http.HttpRequest, pk):
    try:
        user: MyUser = MyUser.objects.get(pk=pk)
    except Exception:
        return JsonResponse({"user": {}})
    balance = user.balance
    banned = user.banned
    stamp = user.period
    period = datetime.datetime.fromtimestamp(stamp)
    expiry = period - datetime.datetime.now()
    if expiry.days < 0 and not user.is_admin:
        return JsonResponse({"expired": True})
    telegram_id = user.telegram_id
    trans_count = user.transactions.count()
    trans_paid = user.transactions.filter(settled=True).count()
    trans_unpaid = user.transactions.filter(settled=False).count()
    orders_count = user.orders.count()
    orders_approved = user.orders.filter(settled=True).count()
    orders_unapproved = user.orders.filter(settled=False).count()
    posts = user.posts.count()

    info = {
        "banned": banned,
        "balance": balance, "telegram_id": telegram_id, "trans_count": trans_count,
        "trans_unpaid": trans_unpaid, "trans_paid": trans_paid, "orders_count": orders_count,
        "orders_approved": orders_approved, "orders_unapproved": orders_unapproved,
        "slots": user.slots,
        "posts": posts,
        "admin": user.is_admin,
        "special": user.special,
        "last_post": user.last_post
    }
    return JsonResponse({"user": info})


@csrf_exempt
def create_user(request: http.HttpRequest):
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"})
    telegram_id = request.POST.get("user_id")
    fname = request.POST.get("fname")
    username = request.POST.get("username")
    try:
        user = MyUser.objects.get(
            telegram_id=telegram_id
        )
    except Exception as e:
        user = MyUser.objects.create_user(
            telegram_id=telegram_id, password="default"
        )
        user.save()
    return get_user(request, user.telegram_id)


@csrf_exempt
def promote_user(request: http.HttpRequest):
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"})
    telegram_id = request.POST.get("user_id")
    days = int(request.POST.get("days"))
    period = timedelta(days=days) + datetime.datetime.now()

    try:
        user: MyUser = MyUser.objects.get(
            telegram_id=telegram_id
        )
    except Exception as e:
        user = MyUser.objects.create_user(
            telegram_id=telegram_id, password="default"
        )
    user.special = True
    user.banned = False
    user.period = period.timestamp()
    user.save()
    return JsonResponse({"msg": "OK"})


@csrf_exempt
def ban_user(request: http.HttpRequest):
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"})
    pk = request.POST.get("user_id")
    try:
        user: MyUser = MyUser.objects.get(telegram_id=pk)
    except Exception:
        return JsonResponse({"error": "user not exists"})
    groups: list[TelegramGroup] = TelegramGroup.objects.filter(
        owner=user.telegram_id
    )
    for group in groups:
        group.delete()
    user.delete()
    return JsonResponse({"msg": "OK"})


@csrf_exempt
def unban_user(request: http.HttpRequest):
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"})
    pk = request.POST.get("user_id")
    lang = request.POST.get("loc", "")
    user = MyUser.objects.get(telegram_id=pk)
    user.banned = False
    user.save()
    msg = "user unbanned" if lang == "en" else "User unbanned"
    return JsonResponse({"msg": msg})


def users_dump(request: http.HttpRequest):
    users = MyUser.objects.filter(banned=False)
    data = []
    for user in users:
        user: MyUser
        info = {"username": user.username, "id": user.telegram_id}
        data.append(info)
    return JsonResponse({"users": data})


@csrf_exempt
def update_user_balance(request: http.HttpRequest):
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"})
    pk = request.POST.get("user_id")
    amount = request.POST.get("amount")
    deduct = request.POST.get("charge")
    try:
        user = MyUser.objects.get(telegram_id=pk)
    except:
        return JsonResponse({"error": "user not exists"})
    if deduct:
        user.balance -= float(amount)
    else:
        user.balance += float(amount)
    user.save()
    return JsonResponse({"msg": "OK"})


@csrf_exempt
def update_user_last(request: http.HttpRequest):
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"})
    last = request.POST.get("last")
    user = request.POST.get("user_id")
    effective_user = request.POST.get("effective_user")
    user: MyUser = MyUser.objects.get(pk=user)
    user.last_post = float(last)
    if effective_user:
        user.effective_id = effective_user
    user.save()
    return JsonResponse({"msg": "OK"})
# ------------------------ Product Views --------------------------


def get_products(request: http.HttpRequest):
    products: list[Product] = Product.objects.all()
    attrs = ["title", "description", "product_id", "price", "volume"]
    data = []
    for prod in products:
        info = {attr: getattr(prod, attr) for attr in attrs}
        data.append(info)
    return JsonResponse({"products": data})


@csrf_exempt
def create_product(request: http.HttpRequest):
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"})
    price = request.POST.get("price")
    description = request.POST.get("desc")
    title = request.POST.get("name")
    volume = request.POST.get("volume")
    try:
        prod = Product.objects.create(price=price, description=description, title=title, volume=volume)
    except Exception as e:
        print(e)
        return HttpResponse("fatal")
    else:
        prod.save()
        msg = "Product created"
    return JsonResponse({"msg": msg})


@csrf_exempt
def delete_product(request: http.HttpRequest):
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"})
    product_id = request.POST.get("product_id")
    product = Product.objects.get(product_id=product_id)
    product.delete()
    msg = "product deleted"
    return JsonResponse({"msg": msg})


@csrf_exempt
def update_product(request: http.HttpRequest):
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"})
    price = request.POST.get("price")
    description = request.POST.get("desc")
    title = request.POST.get("name")
    volume = request.POST.get("volume")
    product_id = request.POST.get("product_id")
    product = Product.objects.get(product_id=product_id)
    product.price = price
    product.description = description
    product.title = title
    product.volume = volume
    product.save()
    return JsonResponse({"msg": "product updated"})


def get_product(request: http.HttpRequest, pk):
    products: list[Product] = Product.objects.filter(pk=pk)
    attrs = ["title", "description", "product_id", "price", "volume"]
    data = {}
    for prod in products:
        info = {attr: getattr(prod, attr) for attr in attrs}
        data.update(info)
    return JsonResponse({"product": data})

# ------------------ Transaction views ------------------------------


def get_invoices(request: http.HttpRequest):
    attrs = ["amount", "status", "address", "btcvalue", "received", "txid"]
    products: list[Transaction] = Transaction.objects.all()
    data = []
    for product in products:
        info = {attr: getattr(product, attr) for attr in attrs}
        data.append(info)
    return JsonResponse({"invoices": data})


def get_invoice(request: http.HttpRequest, pk):
    products: list[Transaction] = Transaction.objects.filter(pk=pk)
    data = []
    for product in products:
        info = {attr: getattr(product, attr) for attr in attrs}
        data.append(info)
    return JsonResponse({"invoice": data[0]})


def get_trans_info(trans: list[Transaction]):
    data = []
    for tran in trans:
        info = dict()
        info["status"] = Transaction.STATUS_CHOICES[tran.status + 1][1]
        info["date"] = tran.created_at.strftime("%d/%m/%Y")
        info["paid"] = tran.received or 0
        info["user"] = str(tran.created_by)
        data.append(info)
    return data


def transactions_today(request: http.HttpRequest):
    transactions: list[Transaction] = Transaction.objects.filter(
        created_at__gte=datetime.date.today()
    )
    data = get_trans_info(transactions)
    return JsonResponse({"transactions": data})


def transactions_weekly(request: http.HttpRequest):
    transactions: list[Transaction] = Transaction.objects.filter(
        created_at__gte=datetime.datetime.now() - timedelta(days=7)
    )
    data = get_trans_info(transactions)
    return JsonResponse({"transactions": data})


def transactions_monthly(request: http.HttpRequest):
    transactions: list[Transaction] = Transaction.objects.filter(
        created_at__gte=datetime.datetime.now() - timedelta(days=30)
    )
    data = get_trans_info(transactions)
    return JsonResponse({"transactions": data})


def transactions_all(request: http.HttpRequest):
    transactions = Transaction.objects.all()
    data = get_trans_info(transactions)
    return JsonResponse({"transactions": data})


def exchanged_rate(amount):
    url = "https://www.blockonomics.co/api/price?currency=USD"
    r = requests.get(url)
    response = r.json()
    rate = response["price"]
    return (float(amount) / rate), rate


def track_invoice(request, pk):
    try:
        invoice = Transaction.objects.get(order_id=pk)
    except Exception as e:
        data = {}
        return JsonResponse({"data": data})
    data = {
        "order_id": invoice.order_id,
        "bits": invoice.btcvalue,
        "value": invoice.amount,
        "addr": invoice.address,
        "status": Transaction.STATUS_CHOICES[invoice.status + 1][1],
        "invoice_status": invoice.status,
    }
    if invoice.received:
        data["paid"] = invoice.received
    else:
        data["paid"] = 0
    # return render(request, "invoice.html", context=data)
    return JsonResponse({"data": data})


@csrf_exempt
def create_payment(request: http.HttpRequest):
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"})
    user_id = request.POST.get("user_id")
    amount = request.POST.get("amount")
    user = MyUser.objects.get(telegram_id=user_id)
    url = "https://www.blockonomics.co/api/new_address?reset=1"
    headers = {"Authorization": "Bearer " + settings.API_KEY}
    r = requests.post(url, headers=headers)
    if r.status_code == 200:
        address = r.json()["address"]
        bits, btcrate = exchanged_rate(amount)
        order_id = uuid.uuid1()
        invoice = Transaction.objects.create(
            order_id=order_id, address=address, btcvalue=bits,
            created_by=user, rate=btcrate * 1e-8, amount=amount
        )
        data = {
            "link": reverse("payments:track_payment", kwargs={"pk": invoice.id}),
            "address": address,
            "btc_price": bits,
            "order_id": order_id,
            "msg": False
        }
    else:
        data = {
            "msg": r.reason
        }
    return JsonResponse({"data": data})


def receive_payment(request: http.HttpRequest):
    if request.method != "GET":
        return
    txid = request.GET.get("txid")
    value = request.GET.get("value")
    status = request.GET.get("status")
    addr = request.GET.get("addr")

    invoice = Transaction.objects.get(address=addr)
    invoice.status = int(status)
    if int(status) == 2:
        invoice.received = (invoice.rate * int(value))
        cpath = BASE_DIR / "tg_bot/config.toml"
        with open(cpath, encoding="utf8") as file:
            cfg = toml.load(file)
            token = cfg["Telegram"]["token"]
        bot = telegram.Bot(token=token)
        bot.get_me()
        msg = f"Your payment of {invoice.received} shekels has been confirmed and your funds will be credited shortly"
        user_id = int(invoice.created_by.telegram_id)
        bot.send_message(user_id, msg)
        invoice.created_by.balance += invoice.received
        invoice.created_by.save()
    invoice.txid = txid
    invoice.save()
    return HttpResponse(200)


# ------------------ Order Views ---------------------------
@csrf_exempt
def create_order(request: http.HttpRequest):
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"})
    product_id = request.POST.get("product_id")
    coupon_code = request.POST.get("coupon")
    qty = request.POST.get("qty")
    user_id = request.POST.get("user")
    if coupon_code:
        coupon: Coupon = Coupon.objects.get(code=coupon_code)
    user = MyUser.objects.get(telegram_id=user_id)
    product: Product = Product.objects.get(product_id=product_id)
    if coupon_code:
        order: Order = Order.objects.create(coupon=coupon, product=product, quantity=qty, user=user)
    else:
        order: Order = Order.objects.create(product=product, quantity=qty, user=user)
    order.save()
    # TODO send notification to admins
    return JsonResponse({"msg": "order created"})


def pending_users_orders(request: http.HttpRequest, user_id):
    orders: list[Order] = Order.objects.filter(user=user_id).filter(settled=False).select_related()
    if not orders:
        return JsonResponse({"orders": []})
    orderlist = []
    for order in orders:
        info = dict()
        info["date"] = order.date.strftime("%d/%m/%Y")
        info["product"] = order.product.title
        info["paid"] = order.actual_price
        info["volume"] = order.product.volume
        orderlist.append(info)
    return JsonResponse({"orders": orderlist})


def settled_users_orders(request: http.HttpRequest, user_id):
    orders: list[Order] = Order.objects.filter(user=user_id).filter(settled=True).select_related()
    if not orders:
        return JsonResponse({"orders": []})
    orderlist = []
    for order in orders:
        info = dict()
        info["date"] = order.date.strftime("%d/%m/%Y")
        info["product"] = order.product.title
        info["paid"] = order.actual_price
        info["volume"] = order.product.volume
        orderlist.append(info)
    return JsonResponse({"orders": orderlist})


def approve_order(request: http.HttpRequest):
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"})
    order_id = request.POST.get("order_id")
    order: Order = Order.objects.get(order_id=order_id)
    order.settled = True
    order.save()
    return JsonResponse({"msg": "OK"})
