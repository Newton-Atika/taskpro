from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class CustomUserManager(BaseUserManager):

    def create_user(self, email, password=None, **extra_fields):

        if not email:
            raise ValueError("The email address is required.")

        email = self.normalize_email(email)

        user = self.model(
            email=email,
            **extra_fields
        )

        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(self, email, password=None, **extra_fields):

        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")

        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(
            email=email,
            password=password,
            **extra_fields
        )


class CustomUser(AbstractUser):

    # Remove username completely
    username = None

    email = models.EmailField(
        unique=True
    )

    phone_number = models.CharField(
        max_length=20
    )

    full_name = models.CharField(
        max_length=200
    )

    accepted_terms = models.BooleanField(
        default=False
    )

    # Staff information
    legal_name = models.CharField(
        max_length=255,
        blank=True
    )

    id_number = models.CharField(
        max_length=30,
        blank=True
    )

    kra_pin = models.CharField(
        max_length=30,
        blank=True
    )

    # Staff assignment status
    is_assigned = models.BooleanField(
        default=False
    )

    USERNAME_FIELD = "email"

    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def __str__(self):
        return self.email