from PIL import Image
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile
import uuid
import imghdr
from rest_framework.exceptions import ValidationError


def get_file_header(file, size=1024):
    """
    Reads the first `size` bytes of the file to determine its header.
    This function saves the current read pointer position and resets it
    after reading, ensuring the file’s state is maintained.
    """
    current_position = file.tell() if hasattr(file, 'tell') else 0
    header = file.read(size)
    file.seek(current_position)
    return header


def optimize_image(image):
    """
    Optimizes an image for product uploads. Converts image to RGB for consistency,
    creates a thumbnail that fits within 800x800 pixels, and saves the image with appropriate
    optimization parameters. Raises a ValidationError if the image cannot be opened.
    """
    try:
        img = Image.open(image)
        img = img.convert("RGB")
    except Exception as e:
        raise ValidationError(f"Invalid image file: {str(e)}")
    
    max_size = (800, 800)
    img.thumbnail(max_size, Image.Resampling.LANCZOS)

    buffer = BytesIO()
    img_format = img.format if img.format is not None else 'JPEG'
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


def process_uploaded_file(file):
    """
    Validates and optimizes an uploaded image file:
      - Checks that file size is within the 10 MB limit.
      - Reads a header from the file via `get_file_header()` without interfering
        with the file's current pointer.
      - Validates the image type against allowed types.
      - Optimizes the image using optimize_image().
    """
    MAX_SIZE = 10 * 1024 * 1024  # 10 MB
    ALLOWED_TYPES = ['jpeg', 'jpg', 'png', 'gif']

    if file.size > MAX_SIZE:
        raise ValidationError("Image size should not exceed 10 MB.")
    
    header = get_file_header(file, 1024)
    ext = imghdr.what(None, header)
    if ext not in ALLOWED_TYPES:
        raise ValidationError("Unsupported image type. Please use jpeg, jpg, png, or gif.")

    try:
        optimized_file = optimize_image(file)
    except Exception as e:
        raise ValidationError(f"Failed to optimize image: {str(e)}")
    
    return optimized_file


def validate_uploaded_file(file):
    """
    Validates an uploaded image file (without optimizing it):
      - Checks file size and validates its type using a header read via get_file_header().
    """
    MAX_SIZE = 10 * 1024 * 1024  # 10 MB
    ALLOWED_TYPES = ['jpeg', 'jpg', 'png', 'gif']

    if file.size > MAX_SIZE:
        raise ValidationError("Image size should not exceed 10 MB.")

    header = get_file_header(file, 1024)
    ext = imghdr.what(None, header)
    if ext not in ALLOWED_TYPES:
        raise ValidationError("Unsupported image type. Please use jpeg, jpg, png, or gif.")