from django.db import models
from users.models import User
from mptt.models import MPTTModel, TreeForeignKey
from utils.slug_utils import unique_slugify
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Q

from cloudinary_storage.storage import MediaCloudinaryStorage

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
        'self', 
        on_delete=models.CASCADE,
        null=True, 
        blank=True,
        related_name='children',
        verbose_name="Parent Category",
    )

    def save(self, *args, **kwargs):

        if not self.pk:
            self.slug = unique_slugify(self.name)[:50]

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
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.1)]
    )
    stock = models.PositiveIntegerField(
        validators=[
            MinValueValidator(1),
            MaxValueValidator(10000)
        ]
    )
    condition = models.CharField(
        max_length=20, choices=CONDITION_CHOICES, default='new'
    )
    is_active = models.BooleanField(default=True)
    units_sold = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    category = models.ForeignKey(
        Category, 
        on_delete=models.CASCADE,
        related_name='products'
    )
        
    def save(self, *args, **kwargs):
        if not self.pk:
            self.slug = unique_slugify(self.name)[:50]
        
        super().save(*args, **kwargs)
    

    # def clean(self):
    #     super().clean()
    #     if self.pk:
    #         original = Product.objects.get(pk=self.pk)
    #         if original.seller != self.seller:
    #             raise ValidationError({'seller': "Changing the seller is not permitted."})

    def __str__(self):
        return self.name

class ProductMedia(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='media'
    )
    image = models.ImageField(
        upload_to="product_images/",
        storage=MediaCloudinaryStorage(),
    )
    is_feature = models.BooleanField(
        default=False,
        help_text="Thumbnail picture"
    )
    created_at = models.DateTimeField(auto_now_add=True)


    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['product'],
                condition=Q(is_feature=True),
                name='unique_featured_image_per_product'
            )
        ]

    def __str__(self):
        return f"Media for {self.product.name}"
