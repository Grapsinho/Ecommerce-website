from django.urls import path
from .views import ReviewListCreateAPIView, ReviewDetailAPIView

urlpatterns = [
    path('shop/items/<slug:slug>/reviews/', ReviewListCreateAPIView.as_view(), name='review-list-create'),
    path('shop/items/<slug:slug>/reviews/<int:review_id>/', ReviewDetailAPIView.as_view(), name='review-detail'),
]