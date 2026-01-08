# 📚 Book Translation Tool (with Gemini API)

A Python tool to translate books using Google Gemini AI. Supports **PDF files** and **Kindle Web** (read.amazon.com).

## ✨ Features

### PDF Translation

- 📄 **PDF Support:** Translate PDF documents page-by-page
- 🧠 **Context Preservation:** Uses previous translations as context for consistency
- 📝 **Structured Output:** Saves translations in JSON Lines (`.jsonl`) format

### Kindle Web Translation (NEW)

- 📸 **Screen Capture:** Automatically captures each page from Kindle Web
- 👁️ **OCR with Gemini Vision:** Extracts text from screenshots using AI
- 🔄 **Resume Support:** Can resume interrupted translations
- ⌨️ **Auto Navigation:** Uses keyboard to flip pages automatically

### Common Features

- 🔁 **Auto Retry:** Handles API rate limits with exponential backoff
- 📊 **Detailed Logging:** Timestamped logs for progress tracking

---

## 🚀 Installation

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/gemini-book-translator.git
cd gemini-book-translator
```

### 2. Create virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux
# or: .\.venv\Scripts\activate  # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Playwright browser (for Kindle translation)

```bash
playwright install chromium
```

### 5. Configure API Key

```bash
cp .env.example .env
```

Edit `.env` and add your [Google Gemini API key](https://aistudio.google.com/app/api-keys):

```
API_KEY=your_gemini_api_key_here
```

---

## 📖 Usage

### PDF Translation

```bash
python bookTranslation.py
```

Follow the prompts to:

1. Enter PDF filename
2. Enter output filename (`.jsonl`)
3. Enter prompt file (e.g., `prompts/prompt_th.txt`)

### Kindle Web Translation

```bash
python kindleTranslation.py
```

Steps:

1. **Login** - Sign in to Amazon in the browser window
2. **Select Book** - Click on a book in your library
3. **Position** - Navigate to the starting page
4. **Start** - Press Enter to begin translation

> ⚠️ **Disclaimer:** Kindle translation is for personal use only. May violate Amazon's Terms of Service.

---

## 📁 Prompt Files

| File                     | Translation Direction |
| ------------------------ | --------------------- |
| `prompts/prompt_th.txt`  | English → Thai        |
| `prompts/prompt_ing.txt` | Italian → English     |
| `prompts/prompt_it.txt`  | English → Italian     |
| `prompts/prompt_ocr.txt` | OCR (text extraction) |

---

## 📤 Output Format

Translations are saved as `.jsonl` files:

```json
{
  "page_number": 1,
  "status": "success",
  "original_text": "The original text...",
  "translated_text": "ข้อความที่แปลแล้ว...",
  "error_message": null
}
```

For Kindle translation, screenshots are saved in `screenshots/` folder.

---

## 🛠️ Project Structure

```
gemini-book-translator/
├── bookTranslation.py     # PDF translation script
├── kindleTranslation.py   # Kindle Web translation script
├── kindle_reader.py       # Browser automation for Kindle
├── vision_ocr.py          # OCR using Gemini Vision API
├── utils.py               # Utility functions
├── prompts/               # Translation prompt templates
│   ├── prompt_th.txt      # English → Thai
│   ├── prompt_ing.txt     # Italian → English
│   └── prompt_ocr.txt     # OCR prompt
├── requirements.txt       # Python dependencies
└── .env.example           # Environment template
```

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.
