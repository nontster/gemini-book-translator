import logging

logger = logging.getLogger(__name__)

def input_name_file(prompt_message: str, type_file: str) -> str:
    """
    It asks the user to enter a file name and ensures that it has the correct extension.

    Args:
        prompt_message (str): message to display to the user.
        type_file (str): the desired file extension (e.g. “.pdf”).

    Returns:
        str: the file name with the correct extension.
    """
    name_file = ""
    while True:
        name_file = input(f"{prompt_message}: ")
        if not name_file.strip():
            logger.warning("The file name cannot be empty. Please try again.")
            continue
        
        if not name_file.lower().endswith(type_file):
            name_file += type_file
            
        break
    return name_file

def import_text(name_file: str) -> str:
    """
    Reads the contents of a text file.

    Args:
        name_file (str): the name of the file to be read.

    Returns:
        str: the file content as a string.
    """
    with open(name_file, 'r', encoding='utf-8') as f:
        prompt = f.read()
    return prompt
