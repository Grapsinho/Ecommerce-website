from django.apps import AppConfig


class WishlistAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'wishlist_app'

    def ready(self):
        import wishlist_app.signals
