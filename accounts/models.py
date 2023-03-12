import datetime

from django.contrib.auth.models import (
    BaseUserManager, AbstractBaseUser
)
from django.db import models


class MyUserManager(BaseUserManager):
    def create_user(self, telegram_id, password=None,):
        """
        Creates and saves a User with the given telegram_id, date of
        birth and password.
        """
        if not telegram_id:
            raise ValueError('Users must have Telegram ID')

        user = self.model(
            telegram_id=telegram_id,
        )

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, telegram_id, password=None):

        user = self.create_user(
            telegram_id,
            password=password,
        )
        user.is_admin = True
        user.save(using=self._db)
        return user


class MyUser(AbstractBaseUser):
    telegram_id = models.CharField(
        verbose_name="user id (telegram)",
        max_length=20,
        unique=True, primary_key=True, default="1000"
    )
    date_added = models.DateTimeField(default=datetime.datetime.now)
    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)
    balance = models.FloatField(default=float)
    slots = models.IntegerField(default=0)
    banned = models.BooleanField(default=False)
    special = models.BooleanField(default=False)
    objects = MyUserManager()
    effective_id = models.CharField(default=str, max_length=100)
    period = models.FloatField(default=float)
    last_post = models.FloatField(default=float)

    USERNAME_FIELD = 'telegram_id'
    REQUIRED_FIELDS = []

    def __str__(self):
        return f"[{self.telegram_id}]"

    def has_perm(self, perm, obj=None):
        """Does the user have a specific permission?"""
        return True

    def has_module_perms(self, app_label):
        """Does the user have permissions to view the app `app_label`?"""
        # Simplest possible answer: Yes, always
        return True

    @property
    def is_staff(self):
        """Is the user a member of staff?"""
        # Simplest possible answer: All admins are staff
        return self.is_admin
