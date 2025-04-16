from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from users.models import User
from product_management.models import Product

class Review(models.Model):

    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE, 
        related_name='reviews'
    )
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='reviews'
    )
    message = models.TextField()
    rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        validators=[
            MinValueValidator(0.0),
            MaxValueValidator(5.0)
        ]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Enforce one review per product per user.
        constraints = [
            models.UniqueConstraint(fields=['product', 'user'], name='unique_product_review')
        ]

    def __str__(self):
        return f"Review by {self.user.username} on {self.product.name}"