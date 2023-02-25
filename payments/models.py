import datetime
import uuid
from django.utils import timezone
from django.db import models
from django.contrib.auth import get_user_model

UserModel = get_user_model()


def gen_id():
    return uuid.uuid4().int


def gen_id2():
    return uuid.uuid4().hex


class Product(models.Model):
    product_id = models.CharField(max_length=50, default=gen_id)
    title = models.CharField(max_length=50)
    description = models.TextField()
    price = models.FloatField()
    volume = models.IntegerField(default=1, blank=True)

    def __str__(self):
        return self.title


class Order(models.Model):
    order_id = models.CharField(max_length=100, default=gen_id)
    user = models.ForeignKey(UserModel, on_delete=models.SET_NULL, blank=True, null=True, related_name="orders")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="products")
    quantity = models.IntegerField(default=1)  # quantity for the product
    date = models.DateField(default=timezone.now)
    settled = models.BooleanField(default=False)

    @property
    def actual_price(self):
        return self.quantity * self.product.price


class Transaction(models.Model):
    STATUS_CHOICES = (
        (-1, "Not Started"),
        (0, "Unconfirmed"),
        (1, "Partially Confirmed"),
        (2, "Confirmed"),
    )
    amount = models.FloatField()
    created_by = models.ForeignKey(UserModel, on_delete=models.CASCADE, null=True, related_name="transactions")
    status = models.IntegerField(choices=STATUS_CHOICES, default=-1)
    order_id = models.CharField(max_length=250)
    address = models.CharField(max_length=250, blank=True, null=True)
    btcvalue = models.FloatField(blank=True, null=True)
    received = models.FloatField(blank=True, null=True)
    txid = models.CharField(max_length=250, blank=True, null=True)
    rbf = models.IntegerField(blank=True, null=True)
    created_at = models.DateField(default=datetime.date.today)
    rate = models.FloatField(default=0, blank=True)
    settled = models.BooleanField(default=False)


class TelegramGroup(models.Model):
    group_id = models.CharField(max_length=200)
    group_title = models.CharField(max_length=200)
    owner = models.CharField(max_length=1000, default=str)

    def __str__(self):
        return self.group_title


class Post(models.Model):
    owner = models.ForeignKey(UserModel, on_delete=models.CASCADE, related_name="posts")
    content = models.TextField(max_length=5000)
    media = models.CharField(max_length=200)
    date = models.DateField(auto_now_add=True)
    media_type = models.IntegerField(default=0)
    duration = models.CharField(max_length=20, default=str)
    groups = models.CharField(max_length=1000, default=str)
    buttons = models.CharField(max_length=1000, default=str)

    def __str__(self):
        return self.content[:30]


class GroupPermitted(models.Model):
    user = models.ForeignKey(UserModel, related_name="groups", on_delete=models.CASCADE)
    group = models.ManyToManyField(TelegramGroup)


"""class Button(models.Model):
    name = models.CharField(max_length=200)
    link = models.CharField(max_length=200)"""
