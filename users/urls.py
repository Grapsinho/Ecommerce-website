from django.urls import path
from .views import (
    EmailConfirmationView,
    RegisterView,
    LoginUser,
    LogoutUser,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RefreshAccessTokenView,
    create_superuser_view
)

urlpatterns = [
    path('auth/email_confirmation/', EmailConfirmationView.as_view(), name='email-confirmation'),
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', LoginUser.as_view(), name='login'),
    path('auth/logout/', LogoutUser.as_view(), name='logout'),


    path('reset-password-request/', PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('reset-password-confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),

    path('token/refresh/', RefreshAccessTokenView.as_view(), name='token_refresh'),


    # url to create super user in production

    path("create-superuser/", create_superuser_view, name="create-superuser"),
]