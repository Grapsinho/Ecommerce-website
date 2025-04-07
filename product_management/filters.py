import django_filters
from .models import Product

class ProductFilter(django_filters.FilterSet):
    price_min = django_filters.NumberFilter(field_name="price", lookup_expr='gte')
    price_max = django_filters.NumberFilter(field_name="price", lookup_expr='lte')
    condition = django_filters.CharFilter(field_name="condition", lookup_expr='iexact')
    category = django_filters.NumberFilter(field_name="categories__id")

    class Meta:
        model = Product
        fields = ['price_min', 'price_max', 'condition', 'category']
