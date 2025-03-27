from rest_framework.throttling import SimpleRateThrottle

class EmailConfirmationRateThrottle(SimpleRateThrottle):
    scope = 'email_confirmation'
    
    def get_cache_key(self, request, view):
        email = request.data.get('email')
        if not email:
            return None  # If no email is provided, don't apply throttling

        return f'email_confirmation_{email}'