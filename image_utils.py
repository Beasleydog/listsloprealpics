"""
Image utility functions for resizing images to specific file sizes and optimizing thumbnails.
"""

from PIL import Image, ImageOps
import os
from typing import Tuple, Optional
import math


def get_image_file_size(image_path: str) -> int:
    """Get the file size of an image in bytes."""
    return os.path.getsize(image_path)


def resize_image_to_file_size(
    input_path: str,
    output_path: str,
    target_size_bytes: int,
    max_iterations: int = 20,
    quality_range: Tuple[int, int] = (10, 95)
) -> str:
    """
    Resize an image to fit within a specific file size limit.

    Args:
        input_path: Path to input image
        output_path: Path where resized image will be saved
        target_size_bytes: Target file size in bytes
        max_iterations: Maximum number of resize attempts
        quality_range: Min/max JPEG quality range to try

    Returns:
        Path to the resized image

    Raises:
        ValueError: If image cannot be resized to target size
        FileNotFoundError: If input file doesn't exist
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input image not found: {input_path}")

    # Open and convert image to RGB
    with Image.open(input_path) as img:
        img = img.convert('RGB')

    # Get original dimensions
    original_width, original_height = img.size
    current_width, current_height = original_width, original_height

    # Try different quality settings first (less destructive)
    min_quality, max_quality = quality_range

    for quality in range(max_quality, min_quality - 1, -5):
        # Try with current dimensions first
        img.save(output_path, 'JPEG', quality=quality, optimize=True)
        current_size = get_image_file_size(output_path)

        if current_size <= target_size_bytes:
            print(f"Image resized successfully with quality {quality}: {current_size} bytes")
            return output_path

    # If quality adjustment wasn't enough, try resizing dimensions
    scale_factor = 1.0

    for iteration in range(max_iterations):
        # Calculate new dimensions
        new_width = int(current_width * scale_factor)
        new_height = int(current_height * scale_factor)

        # Don't go below 100x100 pixels
        if new_width < 100 or new_height < 100:
            break

        # Resize image
        resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Try different quality settings for this size
        for quality in range(max_quality, min_quality - 1, -5):
            resized_img.save(output_path, 'JPEG', quality=quality, optimize=True)
            current_size = get_image_file_size(output_path)

            if current_size <= target_size_bytes:
                print(f"Image resized successfully: {new_width}x{new_height}, quality {quality}: {current_size} bytes")
                return output_path

        # Reduce scale factor for next iteration
        scale_factor *= 0.9

    # If we couldn't reach the target size, save with minimum quality and size
    final_img = img.resize((100, 100), Image.Resampling.LANCZOS)
    final_img.save(output_path, 'JPEG', quality=min_quality, optimize=True)

    final_size = get_image_file_size(output_path)
    print(f"Image resized to minimum size: 100x100, quality {min_quality}: {final_size} bytes")
    return output_path


def resize_thumbnail_for_youtube(
    input_path: str,
    output_path: str,
    max_file_size_bytes: int = 2000000,  # 2MB YouTube limit
    target_dimensions: Tuple[int, int] = (1280, 720),
    maintain_aspect_ratio: bool = True
) -> str:
    """
    Resize a thumbnail to meet YouTube's requirements.

    YouTube thumbnail requirements:
    - Maximum file size: 2MB
    - Recommended dimensions: 1280x720 (16:9 aspect ratio)
    - Supported formats: JPG, GIF, BMP, PNG
    - Minimum dimensions: 640x360

    Args:
        input_path: Path to input thumbnail image
        output_path: Path where optimized thumbnail will be saved
        max_file_size_bytes: Maximum file size in bytes (default: 2MB)
        target_dimensions: Target dimensions as (width, height)
        maintain_aspect_ratio: Whether to maintain aspect ratio when resizing

    Returns:
        Path to the optimized thumbnail

    Raises:
        ValueError: If thumbnail cannot meet requirements
        FileNotFoundError: If input file doesn't exist
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input thumbnail not found: {input_path}")

    with Image.open(input_path) as img:
        # Convert to RGB if necessary
        if img.mode not in ['RGB', 'RGBA']:
            img = img.convert('RGB')
        elif img.mode == 'RGBA':
            # Create white background for transparent images
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[-1])
            img = background

        original_width, original_height = img.size
        target_width, target_height = target_dimensions

        # Resize to target dimensions first
        if maintain_aspect_ratio:
            # Calculate aspect ratios
            original_aspect = original_width / original_height
            target_aspect = target_width / target_height

            if original_aspect > target_aspect:
                # Image is wider, fit to height
                new_height = target_height
                new_width = int(target_height * original_aspect)
            else:
                # Image is taller, fit to width
                new_width = target_width
                new_height = int(target_width / original_aspect)

            # Resize image
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Crop to exact target dimensions if necessary
            if new_width > target_width:
                left = (new_width - target_width) // 2
                img = img.crop((left, 0, left + target_width, target_height))
            elif new_height > target_height:
                top = (new_height - target_height) // 2
                img = img.crop((0, top, target_width, top + target_height))
        else:
            # Force exact dimensions
            img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)

        # Try saving with different quality settings to meet file size limit
        for quality in range(95, 10, -5):
            img.save(output_path, 'JPEG', quality=quality, optimize=True)
            current_size = get_image_file_size(output_path)

            if current_size <= max_file_size_bytes:
                print(f"Thumbnail optimized successfully: {target_width}x{target_height}, quality {quality}: {current_size} bytes")
                return output_path

        # If still too large, try reducing dimensions
        scale_factor = 0.9
        min_dimension = 640  # YouTube minimum

        while scale_factor > 0.1:  # Prevent infinite loop
            new_width = int(target_width * scale_factor)
            new_height = int(target_height * scale_factor)

            if new_width < min_dimension or new_height < min_dimension:
                break

            resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Try different quality settings
            for quality in range(85, 10, -5):
                resized_img.save(output_path, 'JPEG', quality=quality, optimize=True)
                current_size = get_image_file_size(output_path)

                if current_size <= max_file_size_bytes:
                    print(f"Thumbnail resized and optimized: {new_width}x{new_height}, quality {quality}: {current_size} bytes")
                    return output_path

            scale_factor -= 0.1

        # Last resort: save with minimum quality and size
        final_img = img.resize((min_dimension, min_dimension), Image.Resampling.LANCZOS)
        final_img.save(output_path, 'JPEG', quality=10, optimize=True)

        final_size = get_image_file_size(output_path)
        print(f"Thumbnail saved at minimum requirements: {min_dimension}x{min_dimension}, quality 10: {final_size} bytes")
        return output_path


def get_optimal_thumbnail_size(
    input_path: str,
    max_file_size_bytes: int = 2000000
) -> Tuple[int, int]:
    """
    Calculate optimal thumbnail dimensions to fit within file size limit.

    Args:
        input_path: Path to input image
        max_file_size_bytes: Maximum file size in bytes

    Returns:
        Tuple of (width, height) for optimal dimensions
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input image not found: {input_path}")

    with Image.open(input_path) as img:
        original_width, original_height = img.size
        original_aspect = original_width / original_height

        # Start with YouTube recommended size and work down
        target_width = 1280
        target_height = 720

        # Calculate file size for current dimensions
        temp_path = input_path + "_temp.jpg"
        try:
            img.resize((target_width, target_height), Image.Resampling.LANCZOS).save(
                temp_path, 'JPEG', quality=85, optimize=True
            )
            current_size = get_image_file_size(temp_path)

            if current_size <= max_file_size_bytes:
                return (target_width, target_height)

            # Scale down until we fit
            scale_factor = 0.9
            while scale_factor > 0.1:
                new_width = int(target_width * scale_factor)
                new_height = int(new_width / original_aspect)

                if new_width < 640 or new_height < 360:
                    break

                img.resize((new_width, new_height), Image.Resampling.LANCZOS).save(
                    temp_path, 'JPEG', quality=85, optimize=True
                )
                current_size = get_image_file_size(temp_path)

                if current_size <= max_file_size_bytes:
                    return (new_width, new_height)

                scale_factor -= 0.1

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    # Return minimum YouTube dimensions if we can't calculate optimal
    return (640, 360)


# Convenience functions for common use cases
def resize_image_to_size_kb(input_path: str, output_path: str, target_size_kb: int) -> str:
    """Resize image to a specific size in kilobytes."""
    return resize_image_to_file_size(input_path, output_path, target_size_kb * 1024)


def resize_image_to_size_mb(input_path: str, output_path: str, target_size_mb: float) -> str:
    """Resize image to a specific size in megabytes."""
    return resize_image_to_file_size(input_path, output_path, int(target_size_mb * 1024 * 1024))


def ensure_youtube_thumbnail_compliance(thumbnail_path: str, output_path: Optional[str] = None) -> str:
    """
    Ensure a thumbnail meets YouTube's requirements.
    If output_path is None, overwrites the original file.
    """
    if output_path is None:
        output_path = thumbnail_path

    return resize_thumbnail_for_youtube(thumbnail_path, output_path)


if __name__ == "__main__":
    # Example usage
    print("Image utilities loaded successfully!")

    # Example 1: Resize image to specific file size
    # resize_image_to_file_size("input.jpg", "output.jpg", 500000)  # 500KB

    # Example 2: Optimize thumbnail for YouTube
    # resize_thumbnail_for_youtube("thumbnail.jpg", "optimized_thumbnail.jpg")

    # Example 3: Ensure YouTube compliance (overwrite original)
    # ensure_youtube_thumbnail_compliance("my_thumbnail.jpg")