from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import MinValueValidator
from phonenumber_field.modelfields import PhoneNumberField
import uuid

from django.utils.translation import gettext_lazy as _

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)

class User(AbstractUser):

    id = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True, primary_key=True)

    email = models.EmailField(unique=True, db_index=True)
    full_username = models.CharField(max_length=100, help_text="Full user name (e.g John Doe)")
    avatar = models.ImageField(upload_to='avatars/', default='avatars/default-boy-avatar.jpg', null=True)
    age = models.IntegerField(
        validators=[
            MinValueValidator(18)
        ], 
        help_text="Only store age that 18 or are above 18 (e.g 18, 19, 20...)"
    )
    city = models.CharField(
        max_length=300,
        help_text="City where user wants his products to shipped"
    )
    phone_number = PhoneNumberField(
        unique=True,
        region='GE',
        help_text="User phone number (e.g To contact the seller)"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_username", "age", "city", "phone_number"]

    objects = UserManager()
    
    class Meta:
        verbose_name_plural = _("Users")

    def __str__(self):
        return f"User email: {self.email}"