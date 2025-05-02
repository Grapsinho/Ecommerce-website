from django.contrib import admin
from django.utils.html import format_html
from mptt.admin import DraggableMPTTAdmin

from .models import Product, ProductMedia, Category

class ProductMediaInline(admin.TabularInline):
    model = ProductMedia
    extra = 1
    fields = ('image', 'is_feature')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'price', 'stock', 'condition', 'seller', 'created_at', 'is_active')
    list_filter = ('condition', 'is_active', 'created_at', 'category')
    search_fields = ('name', 'description', 'seller__username')
    ordering = ('-created_at',)
    inlines = [ProductMediaInline]
    # Optionally, add fields to be editable directly in list_display:
    list_editable = ('is_active',)


@admin.register(Category)
class CategoryAdmin(DraggableMPTTAdmin):
    mptt_indent_field = "name"
    list_display = ('tree_actions', 'indented_title', 'slug')
    search_fields = ('name',)


@admin.register(ProductMedia)
class ProductMediaAdmin(admin.ModelAdmin):
    list_display = ('product', 'is_feature', 'created_at')
    list_filter = ('is_feature',)
    search_fields = ('product__name',)
