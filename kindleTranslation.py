"""
Kindle Web Book Translation Tool
Translate books from Kindle Web (read.amazon.com) using screen capture + Gemini Vision API
"""

from google import genai
from google.genai import types
from google.api_core import exceptions as google_exceptions
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import asyncio
import logging
import json
import os
import sys
from pathlib import Path
from datetime import datetime

from kindle_reader import KindleWebReader
from vision_ocr import extract_text_from_image, load_ocr_prompt
from bookTranslation import customize_prompt, translate_page

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger(__name__)


def load_progress(progress_file: str) -> dict:
    """
    Load progress from a previous session.
    
    Args:
        progress_file (str): Path to progress file
        
    Returns:
        dict: Progress data or empty dict if no progress file exists
    """
    if os.path.exists(progress_file):
        with open(progress_file, 'r', encoding='utf-8') as f:
            progress = json.load(f)
            logger.info(f"Loaded progress: {progress['pages_completed']} pages completed")
            return progress
    return {"pages_completed": 0, "last_page": 0}


def save_progress(progress_file: str, pages_completed: int, last_page: int) -> None:
    """
    Save current progress to file.
    
    Args:
        progress_file (str): Path to progress file
        pages_completed (int): Number of pages completed
        last_page (int): Last page number processed
    """
    with open(progress_file, 'w', encoding='utf-8') as f:
        json.dump({
            "pages_completed": pages_completed,
            "last_page": last_page,
            "timestamp": datetime.now().isoformat()
        }, f)


async def process_kindle_book(
    client: genai.Client,
    model_name: str,
    reader: KindleWebReader,
    jsonl_name_file: str,
    prompt_template: str,
    max_pages: int = None,
    progress_file: str = None
) -> None:
    """
    Process a Kindle book by capturing screenshots, extracting text via OCR,
    and translating each page.
    
    Args:
        client (genai.Client): Configured Gemini client
        model_name (str): Model name to use
        reader (KindleWebReader): Initialized Kindle Web reader
        jsonl_name_file (str): Output file path for translations
        prompt_template (str): Translation prompt template
        max_pages (int): Maximum number of pages to process (None = all)
        progress_file (str): Path to progress file for resume capability
    """
    # Load OCR prompt
    ocr_prompt = load_ocr_prompt()
    
    # Load progress if resuming
    progress = {}
    if progress_file:
        progress = load_progress(progress_file)
        
    start_page = progress.get("pages_completed", 0)
    
    # Skip to the starting page if resuming
    if start_page > 0:
        logger.info(f"Resuming from page {start_page + 1}...")
        for i in range(start_page):
            await reader.next_page()
    
    history_it = ""
    history_ing = ""
    page_number = start_page
    consecutive_empty = 0
    max_consecutive_empty = 5  # Stop after 5 consecutive empty pages
    
    logger.info("Starting translation process...")
    logger.info("Press Ctrl+C to stop (progress will be saved)")
    
    try:
        while True:
            page_number += 1
            
            # Check max pages limit
            if max_pages and page_number > max_pages:
                logger.info(f"Reached maximum page limit: {max_pages}")
                break
            
            logger.info(f"\n--- Processing Page {page_number} ---")
            
            status = "undefined"
            extracted_text = None
            translated_page = None
            error_message = None
            
            try:
                # Step 1: Capture screenshot
                screenshot_path = await reader.capture_page(page_number)
                
                # Step 2: Extract text using OCR
                logger.info("Extracting text from screenshot...")
                extracted_text = extract_text_from_image(client, model_name, screenshot_path, ocr_prompt)
                
                if not extracted_text or not extracted_text.strip():
                    consecutive_empty += 1
                    status = "skipped_empty_page"
                    logger.warning(f"Page {page_number} has no extractable text, skipped.")
                    
                    if consecutive_empty >= max_consecutive_empty:
                        logger.warning(f"Reached {max_consecutive_empty} consecutive empty pages. Stopping.")
                        break
                else:
                    consecutive_empty = 0  # Reset counter
                    
                    # Step 3: Translate the extracted text
                    logger.info("Translating extracted text...")
                    current_prompt = customize_prompt(prompt_template, extracted_text, history_it, history_ing)
                    translated_page = translate_page(client, model_name, current_prompt)
                    
                    status = "success"
                    logger.info(f"Page {page_number} successfully translated.")
                    
            except google_exceptions.ResourceExhausted as e:
                logger.error(f"❌ API rate limit reached on page {page_number}: {e}")
                status = 'failed_rate_limit'
                error_message = str(e)
                # Wait before retrying
                logger.info("Waiting 60 seconds before continuing...")
                await asyncio.sleep(60)
                
            except google_exceptions.InvalidArgument as e:
                logger.error(f"❌ Invalid input error for page {page_number}: {e}")
                status = 'failed_invalid_argument'
                error_message = str(e)
                
            except Exception as e:
                logger.error(f"❌ Error processing page {page_number}: {e}")
                status = 'failed_generic_error'
                error_message = str(e)
            
            finally:
                # Update history for context
                if status == "success":
                    history_it = extracted_text
                    history_ing = translated_page
                
                # Save result to JSONL
                result_data = {
                    "page_number": page_number,
                    "status": status,
                    "original_text": extracted_text,
                    "translated_text": translated_page,
                    "error_message": error_message
                }
                
                with open(jsonl_name_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(result_data, ensure_ascii=False) + '\n')
                
                # Save progress
                if progress_file:
                    save_progress(progress_file, page_number, page_number)
            
            # Navigate to next page
            if not await reader.next_page():
                logger.info("Could not navigate to next page. End of book or error.")
                break
            
            # Check if we've reached the last page
            if await reader.is_last_page():
                logger.info("Reached the last page of the book.")
                break
                
    except KeyboardInterrupt:
        logger.info("\n\n⚠️ Process interrupted by user. Progress has been saved.")
        if progress_file:
            logger.info(f"To resume, run the script again with the same output file.")
    
    logger.info(f"\n--- Translation process completed! Total pages: {page_number} ---")


async def main_async():
    """
    Async main function for Kindle Web translation.
    """
    load_dotenv()
    
    # Load API key
    api_key = os.getenv("API_KEY")
    if not api_key:
        raise ValueError("API_KEY not found in .env file.")
    
    model_type = os.getenv("MODEL_TYPE", 'gemini-2.0-flash')
    
    # Configure Gemini with new SDK
    client = genai.Client(api_key=api_key)
    logger.info(f"Using Gemini model: {model_type}")
    
    print("\n" + "="*60)
    print("📚 Kindle Web Book Translator")
    print("="*60)
    
    # Get output file name
    output_file = input("\nEnter output filename (e.g., my_book.jsonl): ").strip()
    if not output_file.endswith('.jsonl'):
        output_file += '.jsonl'
    
    # Get translation prompt file
    prompt_file = input("Enter translation prompt file (default: prompts/prompt_ing.txt): ").strip()
    if not prompt_file:
        prompt_file = "prompts/prompt_ing.txt"
    
    # Load translation prompt
    try:
        with open(prompt_file, 'r', encoding='utf-8') as f:
            prompt_template = f.read()
        logger.info(f"Loaded translation prompt from: {prompt_file}")
    except FileNotFoundError:
        logger.error(f"Prompt file not found: {prompt_file}")
        return
    
    # Get max pages (optional)
    max_pages_input = input("Enter maximum pages to translate (leave empty for all): ").strip()
    max_pages = int(max_pages_input) if max_pages_input else None
    
    # Progress file for resume capability
    progress_file = output_file.replace('.jsonl', '_progress.json')
    
    # Initialize Kindle reader
    reader = KindleWebReader(headless=False)
    
    try:
        # Launch browser
        await reader.launch_browser()
        
        print("\n" + "-"*60)
        print("🔐 STEP 1: Login to Amazon")
        print("-"*60)
        print("Please login to your Amazon account in the browser window.")
        print("Waiting for login...")
        
        if not await reader.wait_for_login(timeout=300):
            logger.error("Login failed or timeout. Please try again.")
            return
        
        print("\n✅ Login successful!")
        
        print("\n" + "-"*60)
        print("📖 STEP 2: Select a Book")
        print("-"*60)
        print("Please click on a book in your library to open it.")
        print("Waiting for book selection...")
        
        if not await reader.wait_for_book_selection(timeout=300):
            logger.error("Book selection timeout. Please try again.")
            return
        
        print("\n✅ Book opened!")
        
        print("\n" + "-"*60)
        print("📝 STEP 3: Position the Book")
        print("-"*60)
        print("Navigate to the page where you want to start the translation.")
        input("Press Enter when ready to begin translation...")
        
        print("\n" + "-"*60)
        print("🚀 Starting Translation Process")
        print("-"*60)
        
        # Start translation
        await process_kindle_book(
            client=client,
            model_name=model_type,
            reader=reader,
            jsonl_name_file=output_file,
            prompt_template=prompt_template,
            max_pages=max_pages,
            progress_file=progress_file
        )
        
        print("\n" + "="*60)
        print(f"✅ Translation complete! Output saved to: {output_file}")
        print(f"📸 Screenshots saved in: screenshots/")
        print("="*60)
        
    finally:
        await reader.close()


def main():
    """
    Entry point for Kindle Web translation.
    """
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\n\nProcess cancelled by user.")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise


if __name__ == "__main__":
    main()
