from django.utils.text import slugify
import uuid

def unique_slugify(name):
    base_slug = slugify(name)
    return f"{base_slug}-{uuid.uuid4().hex[:6]}"