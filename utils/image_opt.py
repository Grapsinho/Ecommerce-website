from PIL import Image
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile
import uuid
import imghdr
from rest_framework.exceptions import ValidationError


def get_cached_file_header(file, size=1024):
    """
    Reads the first `size` bytes of the file and caches the result on the file object.
    This avoids multiple I/O operations if the header is requested several times.
    
    Args:
        file: The file-like object to read from.
        size (int): The number of bytes to read for the header.
    
    Returns:
        bytes: The header bytes of the file.
    """
    if hasattr(file, '_cached_header'):
        return file._cached_header
    current_position = file.tell() if hasattr(file, 'tell') else 0
    header = file.read(size)
    file.seek(current_position)
    file._cached_header = header
    return header

def optimize_image(image):
    """
    Optimizes an image file for uploads:
      - Opens the image and converts it to RGB.
      - Creates a thumbnail (max 800x800) using LANCZOS resampling.
      - Saves the image into an in-memory file, applying quality and optimization
        settings based on the file format.
    
    Args:
        image: A file-like object representing the uploaded image.
    
    Returns:
        InMemoryUploadedFile: A new, optimized image file.
        
    Raises:
        ValidationError: When the image cannot be opened or processed.
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
        # Fallback to JPEG for unsupported or unknown formats.
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
    Validates and optimizes an uploaded image file.
      - Checks file size is below the 10 MB limit.
      - Uses a cached header to determine the file type.
      - Verifies that the file type is allowed.
      - Optimizes the image by calling `optimize_image`.
    
    Args:
        file: The uploaded file.
    
    Returns:
        InMemoryUploadedFile: The optimized image file ready for storage.
    
    Raises:
        ValidationError: If the file size exceeds the limit or if the file type is not allowed.
    """
    MAX_SIZE = 10 * 1024 * 1024  # 10 MB
    ALLOWED_TYPES = ['jpeg', 'jpg', 'png', 'gif']

    if file.size > MAX_SIZE:
        raise ValidationError("Image size should not exceed 10 MB.")
    
    header = get_cached_file_header(file, 1024)
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
    Validates an uploaded image file without modifying or optimizing it.
      - Checks that the file size is within limits.
      - Uses the cached header to verify that the file is of an allowed image type.
    
    Args:
        file: The uploaded image file.
    
    Raises:
        ValidationError: If the file size exceeds 10 MB or if the file type is unsupported.
    """
    MAX_SIZE = 10 * 1024 * 1024  # 10 MB
    ALLOWED_TYPES = ['jpeg', 'jpg', 'png', 'gif']

    if file.size > MAX_SIZE:
        raise ValidationError("Image size should not exceed 10 MB.")
    
    header = get_cached_file_header(file, 1024)
    ext = imghdr.what(None, header)
    if ext not in ALLOWED_TYPES:
        raise ValidationError("Unsupported image type. Please use jpeg, jpg, png, or gif.")