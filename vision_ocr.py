"""
Vision OCR Module - Extract text from images using Gemini Vision API
"""

from google import genai
from google.genai import types
from google.api_core import exceptions as google_exceptions
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from PIL import Image
from pathlib import Path
import logging
import os
import base64

logger = logging.getLogger(__name__)


def load_ocr_prompt(prompt_file: str = "prompts/prompt_ocr.txt") -> str:
    """
    Load the OCR prompt from file.
    
    Args:
        prompt_file (str): Path to the prompt file
        
    Returns:
        str: The OCR prompt content
    """
    try:
        with open(prompt_file, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        logger.warning(f"OCR prompt file not found at {prompt_file}, using default prompt")
        return "Extract all text from this book page image. Preserve the original formatting and structure."


def preprocess_image(image_path: str, max_size: tuple = (1920, 1080)) -> Image.Image:
    """
    Preprocess image before sending to Vision API.
    
    Args:
        image_path (str): Path to the image file
        max_size (tuple): Maximum dimensions (width, height)
        
    Returns:
        Image.Image: Processed PIL Image
    """
    img = Image.open(image_path)
    
    # Convert to RGB if necessary (for PNG with transparency)
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')
    
    # Resize if too large while maintaining aspect ratio
    if img.width > max_size[0] or img.height > max_size[1]:
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        logger.debug(f"Image resized to {img.size}")
    
    return img


def image_to_base64(image_path: str) -> tuple:
    """
    Convert image file to base64 string.
    
    Args:
        image_path (str): Path to the image file
        
    Returns:
        tuple: (base64_string, mime_type)
    """
    # Determine mime type
    ext = Path(image_path).suffix.lower()
    mime_types = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.webp': 'image/webp'
    }
    mime_type = mime_types.get(ext, 'image/png')
    
    with open(image_path, 'rb') as f:
        image_data = f.read()
    
    return base64.b64encode(image_data).decode('utf-8'), mime_type


@retry(
    wait=wait_exponential(multiplier=1, min=4, max=60),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type(google_exceptions.ResourceExhausted),
    reraise=True
)
def extract_text_from_image(
    client: genai.Client,
    model_name: str,
    image_path: str,
    prompt: str = None
) -> str:
    """
    Extract text from an image using Gemini Vision API.
    
    Args:
        client (genai.Client): Configured Gemini client
        model_name (str): Model name to use
        image_path (str): Path to the image file
        prompt (str): Optional custom prompt for OCR
        
    Returns:
        str: Extracted text from the image
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")
    
    # Preprocess image
    preprocess_image(image_path)
    
    # Use default or custom prompt
    if prompt is None:
        prompt = load_ocr_prompt()
    
    logger.debug(f"Sending image {image_path} to Gemini Vision API")
    
    # Read image file directly
    with open(image_path, 'rb') as f:
        image_data = f.read()
    
    # Determine mime type
    ext = Path(image_path).suffix.lower()
    mime_types = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.webp': 'image/webp'
    }
    mime_type = mime_types.get(ext, 'image/png')
    
    # Create image part for new SDK
    image_part = types.Part.from_bytes(data=image_data, mime_type=mime_type)
    
    # Send to Gemini Vision API using new SDK
    response = client.models.generate_content(
        model=model_name,
        contents=[prompt, image_part]
    )
    
    extracted_text = response.text.strip()
    
    if not extracted_text:
        logger.warning(f"No text extracted from image: {image_path}")
        return ""
    
    logger.info(f"Successfully extracted {len(extracted_text)} characters from image")
    return extracted_text


def extract_text_from_bytes(
    client: genai.Client,
    model_name: str,
    image_bytes: bytes,
    prompt: str = None,
    mime_type: str = "image/png"
) -> str:
    """
    Extract text from image bytes using Gemini Vision API.
    
    Args:
        client (genai.Client): Configured Gemini client
        model_name (str): Model name to use
        image_bytes (bytes): Image data as bytes
        prompt (str): Optional custom prompt for OCR
        mime_type (str): MIME type of the image
        
    Returns:
        str: Extracted text from the image
    """
    from io import BytesIO
    
    # Load image from bytes for preprocessing
    img = Image.open(BytesIO(image_bytes))
    
    # Convert to RGB if necessary
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')
    
    # Use default or custom prompt
    if prompt is None:
        prompt = load_ocr_prompt()
    
    logger.debug("Sending image bytes to Gemini Vision API")
    
    # Create image part for new SDK
    image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
    
    # Send to Gemini Vision API using new SDK
    response = client.models.generate_content(
        model=model_name,
        contents=[prompt, image_part]
    )
    
    extracted_text = response.text.strip()
    
    if not extracted_text:
        logger.warning("No text extracted from image bytes")
        return ""
    
    logger.info(f"Successfully extracted {len(extracted_text)} characters from image")
    return extracted_text
