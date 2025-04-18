from django.db import models
from users.models import User
from product_management.models import Product

class Wishlist(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='wishlist',
        help_text="The owner of this wishlist."
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        return f"Wishlist for {self.user.username}"

class WishlistItem(models.Model):
    wishlist = models.ForeignKey(
        Wishlist,
        on_delete=models.CASCADE,
        related_name='items',
        help_text="The wishlist this item belongs to."
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='wishlist_items',
        help_text="The product that was wished for."
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'wishlist'],
                name='unique_product_wishlist'
            )
        ]
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product']),
        ]

    def __str__(self):
        return f"{self.product.name} in {self.wishlist.user.username}'s wishlist"
