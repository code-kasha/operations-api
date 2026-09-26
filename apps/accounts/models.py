from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """Authentication identity; staff.Employee holds business roles and employment details."""
