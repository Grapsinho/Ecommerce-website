from django.urls import path
from .views import (
    WishlistRetrieveAPIView,
    WishlistAddProductAPIView,
    WishlistRemoveProductAPIView
)

app_name = 'wishlist'

urlpatterns = [
    path('', WishlistRetrieveAPIView.as_view(), name='wishlist_detail'),
    path('add/', WishlistAddProductAPIView.as_view(), name='wishlist_add'),
    path('remove/', WishlistRemoveProductAPIView.as_view(), name='wishlist_remove'),
]