"""Image Processing Utilities for Jefrey Vision Module."""

import os
import cv2
import numpy as np
from typing import Optional, Dict, Any


def load_image(image_path: str, convert_rgb: bool = True) -> Optional[np.ndarray]:
    """Load an image from file path.
    
    Args:
        image_path: Path to image file
        convert_rgb: Convert BGR to RGB color space
        
    Returns:
        Loaded image as numpy array, or None if failed
    """
    if not os.path.exists(image_path):
        print(f"Error: Image not found at {image_path}")
        return None
    
    try:
        image = cv2.imread(image_path)
        if image is None:
            print(f"Error: Could not read image at {image_path}")
            return None
        
        if convert_rgb:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        return image
    except Exception as e:
        print(f"Error loading image: {e}")
        return None


def resize_image(image: np.ndarray, max_width: int = 800, max_height: int = 600) -> np.ndarray:
    """Resize image while maintaining aspect ratio.
    
    Args:
        image: Input image array
        max_width: Maximum width in pixels
        max_height: Maximum height in pixels
        
    Returns:
        Resized image array
    """
    height, width = image.shape[:2]
    
    # Calculate scaling ratio
    ratio = min(max_width / width, max_height / height)
    
    if ratio >= 1.0:
        # Image is already smaller than max dimensions
        return image
    
    new_width = int(width * ratio)
    new_height = int(height * ratio)
    
    return cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)


def save_image(image: np.ndarray, output_path: str, format: str = "jpg") -> bool:
    """Save image to file path.
    
    Args:
        image: Image array to save
        output_path: Output file path
        format: Output format ('jpg' or 'png')
        
    Returns:
        True if saved successfully, False otherwise
    """
    try:
        # Convert RGB back to BGR for OpenCV save
        if image.shape[2] == 3:
            image_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        else:
            image_bgr = image
        
        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        success = cv2.imwrite(output_path, image_bgr)
        return success
    except Exception as e:
        print(f"Error saving image: {e}")
        return False


def get_image_info(image_path: str) -> Optional[Dict[str, Any]]:
    """Get image metadata information.
    
    Args:
        image_path: Path to image file
        
    Returns:
        Dictionary with image info, or None if failed
    """
    image = load_image(image_path, convert_rgb=False)
    if image is None:
        return None
    
    height, width = image.shape[:2]
    channels = image.shape[2] if len(image.shape) > 2 else 1
    
    # Get file size
    file_size = os.path.getsize(image_path) if os.path.exists(image_path) else 0
    
    return {
        "width": width,
        "height": height,
        "channels": channels,
        "file_size": file_size,
        "format": os.path.splitext(image_path)[1].lower().lstrip("."),
    }


def validate_image(image_path: str, max_size: int = 10 * 1024 * 1024) -> bool:
    """Validate image file.
    
    Args:
        image_path: Path to image file
        max_size: Maximum allowed file size in bytes (default: 10MB)
        
    Returns:
        True if image is valid, False otherwise
    """
    # Check file exists
    if not os.path.exists(image_path):
        return False
    
    # Check file size
    file_size = os.path.getsize(image_path)
    if file_size > max_size:
        return False
    
    # Check file extension
    valid_extensions = [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"]
    ext = os.path.splitext(image_path)[1].lower()
    if ext not in valid_extensions:
        return False
    
    # Try to load image
    image = load_image(image_path, convert_rgb=False)
    if image is None:
        return False
    
    # Check image dimensions
    if image.size == 0:
        return False
    
    return True