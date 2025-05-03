import datetime
from collections import defaultdict, Counter

from django.utils import timezone
from django.db.models import Prefetch, Case, When, IntegerField, Value

from product_management.models import Product, Category, ProductMedia
from product_cart.models import CartItem
from wishlist_app.models import WishlistItem
from orders.models import OrderItem


class Recommendations:
    CART_WEIGHT = 3
    WISHLIST_WEIGHT = 2
    LOOKBACK_DAYS = 180

    @staticmethod
    def for_user(user, limit=10):
        """
        Return up to `limit` product recommendations based on cart and wishlist signals
        (weighted by category), falling back to bestsellers. Excludes user's own,
        purchased (last 6 months), cart, and wishlist items.
        """
        limit = int(limit)
        cutoff = timezone.now() - datetime.timedelta(days=Recommendations.LOOKBACK_DAYS)

        # 1. Exclude products: recent purchases, cart, wishlist
        purchased_ids = set(
            OrderItem.objects
                      .filter(order__user=user, order__created_at__gte=cutoff)
                      .values_list('product_id', flat=True)
        )
        cart_data = list(
            CartItem.objects.filter(cart__user=user)
                    .values_list('product_id', 'product__category_id', 'product__category__parent_id')
        )
        wishlist_data = list(
            WishlistItem.objects.filter(wishlist__user=user)
                        .values_list('product_id', 'product__category_id', 'product__category__parent_id')
        )
        cart_ids = {pid for pid, *_ in cart_data}
        wishlist_ids = {pid for pid, *_ in wishlist_data}
        excluded_ids = purchased_ids | cart_ids | wishlist_ids

        # 2. Compute weights and excluded children per parent group
        cat_weights = Counter()
        excluded_children = defaultdict(set)
        for pid, cat_id, parent_id in cart_data:
            group_id = parent_id or cat_id
            cat_weights[group_id] += Recommendations.CART_WEIGHT
            excluded_children[group_id].add(cat_id)
        for pid, cat_id, parent_id in wishlist_data:
            group_id = parent_id or cat_id
            cat_weights[group_id] += Recommendations.WISHLIST_WEIGHT
            excluded_children[group_id].add(cat_id)

        # 3. Base queryset with exclusions and eager loading of featured media
        feature_prefetch = Prefetch(
            'media', queryset=ProductMedia.objects.filter(is_feature=True), to_attr='feature_media'
        )
        base_qs = (
            Product.objects
                   .filter(is_active=True, stock__gt=0)
                   .exclude(seller=user)
                   .exclude(id__in=excluded_ids)
                   .prefetch_related(feature_prefetch)
        )

        # 4. If no signals, fallback directly
        if not cat_weights:
            return base_qs.order_by('-units_sold')[:limit]

        # 5. Batch-fetch child categories for all parent groups
        group_ids = list(cat_weights.keys())
        flat_excluded = {c for cats in excluded_children.values() for c in cats}
        raw_children = Category.objects.filter(parent_id__in=group_ids)\
                                     .exclude(id__in=flat_excluded)\
                                     .values_list('id', 'parent_id')

        # 6. Build weight map for each child category
        weight_map = {cid: cat_weights[parent_id] for cid, parent_id in raw_children}

        # 7. Annotate score and order by score, units_sold, average_rating
        cases = [When(category_id=cid, then=Value(wt)) for cid, wt in weight_map.items()]
        recs = (
            base_qs
            .annotate(score=Case(*cases, default=Value(0), output_field=IntegerField()))
            .order_by('-score', '-units_sold', '-average_rating')[:limit]
        )

        return recs