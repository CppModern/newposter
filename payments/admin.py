from django.contrib import admin
from .models import *
# Register your models here.
admin.site.register(Product)
admin.site.register(TelegramGroup)
admin.site.register(GroupPermitted)
admin.site.register(Post)
admin.site.register(Order)
admin.site.register(Transaction)
