import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from PyPDF2 import PdfReader
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from utils import input_name_file, import_text
import logging
import time
import json
import os

logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%H:%M:%S",
    )

logger = logging.getLogger(__name__)

def customize_prompt(prompt: str, page_to_translate: str, history_it: str, history_ing: str) -> str:
    """
    Create the complete prompt for the model, including the context of the previous translation.
    
    Args:
        prompt (str): original prompt
        page_to_translate (str): single page of text to be translated
        history_it (str): previous text not translated
        history_ing (str): previous text just translated 
    
    Returns: 
        str: Prompt updated with the latest translations
        
    """
    history_section = ""
    if history_it and history_ing:
        history_section = f"""
        ### EXAMPLE OF PREVIOUS TRANSLATION
        
        #### Original Text (Italian):
        {history_it}

        #### Reference Translation (English):
        {history_ing}
        ---
        """

    custom_prompt = f"""
        {prompt}

        {history_section}
        ### TEXT TO BE TRANSLATED
        {page_to_translate}
        """
        
    return custom_prompt

@retry(
    wait=wait_exponential(multiplier=1, min=4, max=60),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type(google_exceptions.ResourceExhausted),
    reraise=True
)
def translate_page(model: genai.GenerativeModel, prompt: str) -> str:
    """
    Sends the prompt to the generative model and returns the translation.
    Retries with exponential backoff on ResourceExhausted errors.
    
    Args:
        model (genai.GenerativeMode): Google AI Studio API generative model
        prompt (str): original prompt
    
    Returns: 
        (str): translated text
    """
    if not prompt.strip():
        raise ValueError("The prompt sent to the model is empty.")

    response = model.generate_content(prompt)
    return response.text

def process_pdf(model: genai.GenerativeModel, pdf_name_file: str, jsonl_name_file: str, prompt_template: str) -> None:
    """
    Process a PDF file, translate each page, and save the results in a JSONL file.
    
    Args:
        model (genai.GenerativeMode): Google AI Studio API generative model
        pdf_name_file (str): name of the PDF file to be translated
        jsonl_name_file (str): name of the jsonl file where translation information is saved
        prompt_template (str): prompt for translation
    
    Returns: 
        (None)
    """
    try:
        reader_pdf = PdfReader(pdf_name_file)
    except FileNotFoundError:
        current_path = os.getcwd()
        raise FileNotFoundError(f"The file “{pdf_name_file}” was not found in {current_path}.")
    
    pages = reader_pdf.pages
    number_pages = len(pages)
    
    if number_pages == 0:
        raise ValueError(f"The PDF file ‘{pdf_name_file}’ does not contain any pages.")

    logger.info(f"The file {pdf_name_file} contains {number_pages} pages that will be translated.")

    history_it = ""
    history_ing = ""

    for i in range(number_pages):
        page_number = i + 1
        logger.info(f"\n--- Translation Page {page_number}/{number_pages} ---")
        
        page = pages[i]
        text_page = page.extract_text()
        
        status = "undefined"
        translated_page = None
        error_message = None
        

        try:
            if not text_page or not text_page.strip():
                status = "skipped_empty_page"
                logger.warning(f"Page {page_number} is blank or has no text, skipped.")
                continue 
            
            current_prompt = customize_prompt(prompt_template, text_page, history_it, history_ing)
            
            translated_page = translate_page(model, current_prompt)
            status = "success"
            logger.info(f"Page {page_number} successfully translated.")
            
        except (google_exceptions.ResourceExhausted, google_exceptions.DeadlineExceeded) as e:
            logger.error(f"❌ Failed to translate page {page_number} after multiple retries: {e}")
            status = 'failed_after_retries'
            error_message = str(e)
        
        except (google_exceptions.InvalidArgument, ValueError) as e:
            logger.error(f"❌ Invalid input error for the page {page_number}: {e}")
            status = 'failed_invalid_argument'
            error_message = str(e)
            
        except Exception as e:
            logger.error(f"❌ Generic error in page translation {page_number}: {e}")
            status = 'failed_generic_error'
            error_message = str(e)
        
        finally:
            if status in ("success", "success_after_retry"):
                history_it = text_page
                history_ing = translated_page
            
            result_data = {
                "page_number": page_number,
                "status": status,
                "original_text_preview": text_page[:100] + '...' if text_page else None,
                "translated_text": translated_page,
                "error_message": error_message
            }
            
            with open(jsonl_name_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(result_data, ensure_ascii=False) + '\n')
    
    logger.info("\n--- Translation process completed! ---")

def main() -> None:
    """
    Main function that orchestrates the translation process.
    """
    try:
        load_dotenv()
        api_key = os.getenv("API_KEY")
        if not api_key:
            raise ValueError("API_KEY not found in file .env.")
            
        model_type = os.getenv("MODEL_TYPE", 'gemini-2.5-flash')
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_type) 
        logger.info(f"Using Gemini model: {model_type}")
        
        logger.info("Welcome to the PDF book translator with Gemini.")
        
        book_name_file = input_name_file(
            prompt_message="Enter the name of the .pdf file to be translated", 
            type_file=".pdf"
        )
        
        jsonl_output_name_file = input_name_file(
            prompt_message="Enter the name of the .jsonl file where you want to save the translation.",
            type_file=".jsonl"
        )

        name_file_prompt = input_name_file(
            prompt_message="Enter the name of the .txt file containing the prompt",
            type_file=".txt"
        )
        
        logger.info("----------------------------------")

        imported_prompt_template = import_text(name_file_prompt)
        
        logger.info(f"Start of the translation process for \"{book_name_file}\". The output will be saved in \"{jsonl_output_name_file}\".")
        
        process_pdf(model, book_name_file, jsonl_output_name_file, imported_prompt_template)

    except (ValueError, FileNotFoundError) as e:
        logger.error(f"\nERROR: {e}")
    except Exception as e:
        logger.error(f"\nUNEXPECTED ERROR: {e}")
        
if __name__ == "__main__":
    main()
