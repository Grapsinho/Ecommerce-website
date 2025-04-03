from rest_framework.throttling import SimpleRateThrottle
from django.core.cache import cache

class EmailConfirmationRateThrottle(SimpleRateThrottle):
    scope = 'email_confirmation'
    
    def get_cache_key(self, request, view):
        email = request.data.get('email')
        if not email:
            return None  # If no email is provided, don't apply throttling

        return f'email_confirmation_{email}'
    

class LoginRateThrottle(SimpleRateThrottle):
    scope = 'anon'
    cache = cache  # Ensures that it uses Redis or a centralized cache backend

    def get_cache_key(self, request, view):
        if request.method != 'POST':
            return None
        ident = request.data.get('email', None)
        if ident:
            ident = ident.lower()
        else:
            ident = self.get_ident(request)
        return self.cache_format % {'scope': self.scope, 'ident': ident}