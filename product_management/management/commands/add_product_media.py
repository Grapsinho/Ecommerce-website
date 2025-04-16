import os
import json
import time
import requests
import cloudinary.uploader

from django.core.management.base import BaseCommand
from product_management.models import Product, ProductMedia

# --- CONFIGURATION ---
# Replace with your Unsplash API key or set as environment variable UNSPLASH_ACCESS_KEY.
UNSPLASH_ACCESS_KEY = os.environ.get("UNSPLASH_ACCESS_KEY")
UNSPLASH_API_URL = "https://api.unsplash.com/search/photos"

# Path to your product fixtures file (make sure this file exists and has valid JSON).
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../../../"))
PRODUCT_FIXTURES_FILE = os.path.join(PROJECT_ROOT, "fixtures", "product_fixtures", "product_fixtures.json")


# Number of images to fetch per product
IMAGES_PER_PRODUCT = 2

def search_unsplash_images(query, per_page=5):
    """
    Search Unsplash for images that match the query.
    Returns a list of image URLs.
    """
    params = {
        "query": query,
        "per_page": per_page,
        "client_id": UNSPLASH_ACCESS_KEY,
    }
    response = requests.get(UNSPLASH_API_URL, params=params)
    if response.status_code == 200:
        data = response.json()
        # Select the 'regular' size URL for each result
        image_urls = [result['urls']['regular'] for result in data.get('results', [])]
        return image_urls
    else:
        print(f"Error querying Unsplash for '{query}': {response.status_code} {response.text}")
        return []

class Command(BaseCommand):
    help = "Automatically add product media by fetching images from Unsplash and uploading them to Cloudinary."

    def handle(self, *args, **options):
        # Load product fixtures JSON file.
        try:
            with open(PRODUCT_FIXTURES_FILE, 'r', encoding='utf-8') as f:
                products = json.load(f)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error loading product fixtures: {str(e)}"))
            return

        self.stdout.write(f"Loaded {len(products)} products from fixture file.")

        for product_fixture in products:
            product_id = product_fixture.get('id')
            product_name = product_fixture.get('fields', {}).get('name')
            if not (product_id and product_name):
                self.stdout.write("Missing product ID or name; skipping.")
                continue

            # Look up the product in the database.
            try:
                product = Product.objects.get(pk=product_id)
            except Product.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"Product id {product_id} not found. Skipping."))
                continue

            self.stdout.write(f"Processing product {product_id}: {product_name}")

            # Search Unsplash for images.
            image_urls = search_unsplash_images(product_name)
            if not image_urls:
                self.stdout.write(self.style.WARNING(f"No images found for product: {product_name}"))
                continue

            # Use at least 2 images if available.
            chosen_urls = (image_urls * IMAGES_PER_PRODUCT)[:IMAGES_PER_PRODUCT] if len(image_urls) < IMAGES_PER_PRODUCT else image_urls[:IMAGES_PER_PRODUCT]

            # For each chosen URL, upload to Cloudinary and create a ProductMedia object.
            for idx, url in enumerate(chosen_urls):
                try:
                    # Cloudinary fetches and stores the image from the remote URL.
                    result = cloudinary.uploader.upload(url)
                    secure_url = result.get('secure_url')
                    if not secure_url:
                        self.stdout.write(self.style.WARNING(f"Cloudinary upload failed for URL: {url}"))
                        continue

                    media_obj = ProductMedia.objects.create(
                        product=product,
                        image=secure_url,
                        is_feature=(True if idx == 0 else False)
                    )
                    self.stdout.write(f"Created ProductMedia id: {media_obj.id} for product {product_id}")
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error uploading image for product {product_name}: {str(e)}"))

            # Sleep briefly to avoid hitting API rate limits.
            time.sleep(0.5)

        self.stdout.write(self.style.SUCCESS("Finished adding product media."))
