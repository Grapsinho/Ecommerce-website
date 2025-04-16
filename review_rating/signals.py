from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Avg, Count
from .models import Review

@receiver([post_save, post_delete], sender=Review)
def update_product_rating(sender, instance, **kwargs):
    product = instance.product
    agg = product.reviews.aggregate(
        avg_rating=Avg('rating'),
        total_reviews=Count('id')
    )
    product.total_reviews = agg['total_reviews'] or 0
    product.average_rating = agg['avg_rating'] or 0
    product.save(update_fields=['average_rating', 'total_reviews'])