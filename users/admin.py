from django.contrib import admin
from .models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _


class CustomUserAdmin(BaseUserAdmin):
    model = User

    # Show on list view (table)
    list_display = (
        "id", "email", "username", "full_username", "is_active", "is_staff", "is_superuser"
    )

    # Make 'id' read-only in admin form
    readonly_fields = ("id",)

    # Customize fieldsets for detail view
    fieldsets = (
        (None, {
            "fields": ("id", "username", "email", "password")
        }),
        (_("Personal info"), {
            "fields": ("first_name", "last_name", "full_username", "avatar", "age", "city", "phone_number")
        }),
        (_("Permissions"), {
            "fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions"),
        }),
        (_("Important dates"), {
            "fields": ("last_login", "date_joined"),
        }),
    )

    # Fields shown when creating a new user via admin
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "username", "password1", "password2"),
        }),
    )

    search_fields = ("email", "username", "full_username", "phone_number")
    ordering = ("email",)


admin.site.register(User, CustomUserAdmin)


from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
from rest_framework_simplejwt.token_blacklist.admin import OutstandingTokenAdmin

admin.site.unregister(OutstandingToken)

@admin.register(OutstandingToken)
class CustomOutstandingTokenAdmin(OutstandingTokenAdmin):
    list_display = ('user', 'jti', 'created_at', 'expires_at')

    actions = ['delete_all_tokens']

    def delete_all_tokens(self, request, queryset):
        queryset.delete()
        self.message_user(request, "Selected tokens have been deleted.")
    delete_all_tokens.short_description = "Delete selected tokens"