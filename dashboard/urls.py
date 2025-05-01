from django.urls import path
from .views import ProfileUpdateView, MyProductListView, RecommendationView

urlpatterns = [
    path('dashboard/profile/current/', ProfileUpdateView.as_view(), name='profile-current'),
    path('dashboard/me/products/', MyProductListView.as_view(), name='my-products'),
    path('dashboard/me/recommendations/', RecommendationView.as_view(), name='recommendations'),
]