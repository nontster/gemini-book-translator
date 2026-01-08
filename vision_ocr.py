"""
Vision OCR Module - Extract text from images using Gemini Vision API
"""

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from PIL import Image
from pathlib import Path
import logging
import os

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


@retry(
    wait=wait_exponential(multiplier=1, min=4, max=60),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type(google_exceptions.ResourceExhausted),
    reraise=True
)
def extract_text_from_image(
    model: genai.GenerativeModel,
    image_path: str,
    prompt: str = None
) -> str:
    """
    Extract text from an image using Gemini Vision API.
    
    Args:
        model (genai.GenerativeModel): Configured Gemini model with vision capability
        image_path (str): Path to the image file
        prompt (str): Optional custom prompt for OCR
        
    Returns:
        str: Extracted text from the image
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")
    
    # Load and preprocess image
    img = preprocess_image(image_path)
    
    # Use default or custom prompt
    if prompt is None:
        prompt = load_ocr_prompt()
    
    logger.debug(f"Sending image {image_path} to Gemini Vision API")
    
    # Send to Gemini Vision API
    response = model.generate_content([prompt, img])
    
    extracted_text = response.text.strip()
    
    if not extracted_text:
        logger.warning(f"No text extracted from image: {image_path}")
        return ""
    
    logger.info(f"Successfully extracted {len(extracted_text)} characters from image")
    return extracted_text


def extract_text_from_bytes(
    model: genai.GenerativeModel,
    image_bytes: bytes,
    prompt: str = None
) -> str:
    """
    Extract text from image bytes using Gemini Vision API.
    
    Args:
        model (genai.GenerativeModel): Configured Gemini model with vision capability
        image_bytes (bytes): Image data as bytes
        prompt (str): Optional custom prompt for OCR
        
    Returns:
        str: Extracted text from the image
    """
    from io import BytesIO
    
    # Load image from bytes
    img = Image.open(BytesIO(image_bytes))
    
    # Convert to RGB if necessary
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')
    
    # Use default or custom prompt
    if prompt is None:
        prompt = load_ocr_prompt()
    
    logger.debug("Sending image bytes to Gemini Vision API")
    
    # Send to Gemini Vision API
    response = model.generate_content([prompt, img])
    
    extracted_text = response.text.strip()
    
    if not extracted_text:
        logger.warning("No text extracted from image bytes")
        return ""
    
    logger.info(f"Successfully extracted {len(extracted_text)} characters from image")
    return extracted_text
