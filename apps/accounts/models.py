from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """Authentication identity; employee records and business roles are planned separately."""
