import os
import cloudinary
import cloudinary.uploader
import cloudinary.api

# Consolidate Cloudinary configuration from environment variables.
CLOUDINARY_CONFIG = {
    'cloud_name': os.environ.get("CLOUDINARY_CLOUD_NAME"),
    'api_key': os.environ.get("CLOUDINARY_API_KEY"),
    'api_secret': os.environ.get("CLOUDINARY_API_SECRET"),
}

# Apply the configuration to Cloudinary.
cloudinary.config(**CLOUDINARY_CONFIG)

# Define the settings for django-cloudinary-storage.
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': CLOUDINARY_CONFIG['cloud_name'],
    'API_KEY': CLOUDINARY_CONFIG['api_key'],
    'API_SECRET': CLOUDINARY_CONFIG['api_secret'],
}

# Set Cloudinary as the default file storage.
DEFAULT_FILE_STORAGE = "cloudinary_storage.storage.MediaCloudinaryStorage"
# As Cloudinary handles your media files, you may leave MEDIA_URL empty.
MEDIA_URL = ""