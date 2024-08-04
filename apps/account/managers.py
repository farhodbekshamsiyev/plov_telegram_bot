from django.contrib.auth.base_user import BaseUserManager
from django.db import models


# Create your models here.
class UserType(models.TextChoices):
    SUPER_ADMIN = 'SUPER_ADMIN', 'Super Admin'
    ADMIN = 'ADMIN', 'Admin'
    TELEGRAM_USER = 'TELEGRAM_USER', 'Telegram User'


class CustomUserManager(BaseUserManager):

    def get_or_create(self, username, password=None, user_type=UserType.TELEGRAM_USER, **extra_fields):
        if self.filter(username=username, user_type=user_type, **extra_fields).exists():
            return self.model.objects.get(username=username), False

        return self.create_user(username, password, **extra_fields), True

    def create_user(self, username, password=None, user_type=UserType.TELEGRAM_USER, **extra_fields):
        if not username:
            raise ValueError('User name is required for admin users')

        if user_type in [UserType.SUPER_ADMIN, UserType.ADMIN]:
            if not password:
                raise ValueError('Password is required for admin users')

        user = self.model(username=username, user_type=user_type, **extra_fields)

        if password:
            user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        return self.create_user(username, password, user_type=UserType.SUPER_ADMIN, **extra_fields)
