from django.apps import AppConfig


class ReviewRatingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'review_rating'

    def ready(self):
        import review_rating.signals