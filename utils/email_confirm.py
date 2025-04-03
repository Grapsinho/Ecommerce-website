from rest_framework_simplejwt.tokens import RefreshToken

def get_email_confirmation_code_key(email):
    return f"email_confirmation_code_{email}"

def get_email_confirmed_key(email):
    return f"email_confirmed_{email}"

def generate_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token), str(refresh)