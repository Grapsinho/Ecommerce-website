from PIL import Image
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile
import uuid

def optimize_image(image):
    img = Image.open(image)
    img = img.convert("RGB")  # Convert all to RGB for consistency
    max_size = (800, 800)
    img.thumbnail(max_size, Image.Resampling.LANCZOS)

    buffer = BytesIO()

    img_format = img.format if img.format else 'JPEG'
    format_lower = img_format.lower()

    if format_lower in ['jpeg', 'jpg']:
        img.save(buffer, format='JPEG', quality=80, optimize=True)
    elif format_lower == 'png':
        img.save(buffer, format='PNG', optimize=True)
    else:
        # Fallback to JPEG if unknown
        img.save(buffer, format='JPEG', quality=80, optimize=True)
        format_lower = 'jpeg'

    buffer.seek(0)

    new_file_name = f"{uuid.uuid4().hex}.{format_lower}"

    optimized_image = InMemoryUploadedFile(
        file=buffer,
        field_name='ImageField',
        name=new_file_name,
        content_type=f'image/{format_lower}',
        size=buffer.getbuffer().nbytes,
        charset=None
    )

    return optimized_image