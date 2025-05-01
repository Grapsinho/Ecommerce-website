from django_filters.rest_framework import FilterSet, NumberFilter
from product_management.models import Product

class MyProductFilter(FilterSet):
    min_price = NumberFilter(field_name='price', lookup_expr='gte')
    max_price = NumberFilter(field_name='price', lookup_expr='lte')
    min_stock = NumberFilter(field_name='stock', lookup_expr='gte')
    max_stock = NumberFilter(field_name='stock', lookup_expr='lte')
    min_units_sold = NumberFilter(field_name='units_sold', lookup_expr='gte')
    max_units_sold = NumberFilter(field_name='units_sold', lookup_expr='lte')

    class Meta:
        model = Product
        fields = [
            'min_price', 'max_price',
            'min_stock', 'max_stock',
            'min_units_sold', 'max_units_sold'
        ]