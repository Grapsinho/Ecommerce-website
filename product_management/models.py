from django.db import models
from users.models import User
from mptt.models import MPTTModel, TreeForeignKey
from utils.slug_utils import unique_slugify
from django.utils.text import slugify

from django.conf import settings

if not settings.DEBUG:
    from cloudinary_storage.storage import MediaCloudinaryStorage
    product_image_storage = MediaCloudinaryStorage()
    default_image = 'product_images/No Image'
    upload_to_path = 'product_image/'
else:
    product_image_storage = None
    default_image = 'product_images/No Image.svg'
    upload_to_path = 'product_images/'


# Product condition choices
CONDITION_CHOICES = (
    ('new', 'New'),
    ('used', 'Used'),
    ('refurbished', 'Refurbished'),
)

class Category(MPTTModel):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, db_index=True)
    parent = TreeForeignKey(
        'self', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='children',
        verbose_name="Parent Category",
    )

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:50]
        
        if not self.slug == slugify(self.name)[:50]:
            self.slug = slugify(self.name)[:50]

        super().save(*args, **kwargs)

    class MPTTMeta:
        order_insertion_by = ['name']

    class Meta:
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name

class Product(models.Model):
    seller = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='products'
    )
    name = models.CharField(max_length=150, db_index=True)
    description = models.TextField(db_index=True)
    slug = models.SlugField(unique=True, db_index=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    condition = models.CharField(
        max_length=20, choices=CONDITION_CHOICES, default='new'
    )
    is_active = models.BooleanField(default=True)
    units_sold = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Many-to-many relationship with categories.
    categories = models.ManyToManyField(Category, related_name='products')


    def clean(self):
        """
        Model-level validations:
          - Ensure price is greater than $0.1.
          - Ensure stock is greater than 1.
          - Prevent seller changes once the product has been created.
        """

        from django.core.exceptions import ValidationError

        # Validate price
        if self.price <= 0.1:
            raise ValidationError({'price': "Price must be greater than $0.1."})
        
        # Validate stock
        if self.stock <= 1:
            raise ValidationError({'stock': "Stock must be greater than 1."})


    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self.name)[:50]

        if not self.slug == unique_slugify(self.name)[:50]:
            self.slug = unique_slugify(self.name)[:50]

        super().save(*args, **kwargs)

    class Meta:
        unique_together = ['seller', 'name']

    def __str__(self):
        return self.name

class ProductMedia(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='media'
    )
    image = models.ImageField(
        upload_to=upload_to_path,
        storage=product_image_storage,
        default=default_image
    )
    is_feature = models.BooleanField(
        default=False,
        help_text="Thumbnail picture"
    )
    created_at = models.DateTimeField(auto_now_add=True)


    def save(self, *args, **kwargs):
        # If this image is marked as featured, unmark others
        if self.is_feature:
            ProductMedia.objects.filter(
                product=self.product, is_feature=True
            ).exclude(pk=self.pk).update(is_feature=False)

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Media for {self.product.name}"
