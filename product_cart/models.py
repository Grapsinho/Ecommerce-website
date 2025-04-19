from decimal import Decimal
from django.conf import settings
from django.db import models, transaction
from django.db.models import F
from django.utils.timezone import now
from django.core.validators import MinValueValidator

class Cart(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cart'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    total_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Cached sum of all items (quantity * unit price)"
    )

    def __str__(self):
        return f"Cart for {self.user.username}"

    def recalc_total(self) -> Decimal:
        """
        Recalculate and save the true cart total by aggregating items.
        """
        agg = self.items.aggregate(
            total=models.Sum(
                F('quantity') * F('unit_price'),
                output_field=models.DecimalField(max_digits=12, decimal_places=2)
            )
        )
        total = agg['total'] or Decimal('0.00')
        if self.total_price != total:
            self.total_price = total
            # updated_at auto-updates
            self.save(update_fields=['total_price'])
        return total

class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey(
        'product_management.Product',
        on_delete=models.CASCADE
    )
    quantity = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Quantity must be at least 1"
    )
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Price at time of adding to cart"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['cart', 'product'], name='unique_cart_product')
        ]
        ordering = ['created_at']

    def __str__(self):
        return f"{self.quantity}x {self.product.name} @ {self.unit_price} in {self.cart}"

    @transaction.atomic
    def save(self, *args, **kwargs):
        # On create, capture the current product price
        is_new = self.pk is None
        old_qty = 0
        if not is_new:
            old_qty = CartItem.objects.values_list('quantity', flat=True).get(pk=self.pk)

        if is_new:
            self.unit_price = self.product.price

        super().save(*args, **kwargs)

        delta = (self.quantity - old_qty) * self.unit_price
        if delta:
            # Update cached total_price and bump updated_at
            Cart.objects.filter(pk=self.cart_id).update(
                total_price=F('total_price') + delta,
                updated_at=now()
            )

    @transaction.atomic
    def delete(self, *args, **kwargs):
        # Subtract this line's full value and bump cart.updated_at
        decrement = self.quantity * self.unit_price
        Cart.objects.filter(pk=self.cart_id).update(
            total_price=F('total_price') - decrement,
            updated_at=now()
        )
        super().delete(*args, **kwargs)