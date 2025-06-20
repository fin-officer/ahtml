# 📦 MetaDoc System - Kompletny Setup Guide

## 🚀 Instalacja i konfiguracja

### 1. **Wymagania systemowe**

```bash
# System: Linux, macOS, Windows
# Python: 3.8+
# RAM: 4GB+ (dla OCR i przetwarzania video)
# Dysk: 1GB+ wolnego miejsca
```

### 3. **Instalacja krok po krok**

```bash
# 2. Utworzenie środowiska wirtualnego
python -m venv venv

# 3. Aktywacja środowiska
# Linux/macOS:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# 4. Instalacja pakietów Python
pip install -r requirements.txt

# 5. Instalacja Tesseract OCR
# Ubuntu/Debian:
sudo apt-get install tesseract-ocr tesseract-ocr-pol
# macOS:
brew install tesseract tesseract-lang
# Windows: pobierz z https://github.com/UB-Mannheim/tesseract/wiki

# 6. Instalacja poppler (dla PDF)
# Ubuntu/Debian:
sudo apt-get install poppler-utils
# macOS:
brew install poppler
# Windows: pobierz z https://github.com/oschwartz10612/poppler-windows
```

### 4. **Struktura projektu**

```
metadoc-system/
├── builder.py                 # CLI Builder (Python)
├── metadoc.html              # Interaktywny viewer (HTML)
├── requirements.txt          # Zależności Python
├── templates/
│   └── base_template.html    # Szablon HTML
├── examples/
│   ├── faktury/              # Przykładowe PDF
│   ├── obrazy/               # Przykładowe zdjęcia
│   └── video/                # Przykładowe nagrania
├── output/                   # Wygenerowane pliki
└── docs/                     # Dokumentacja
```

---

## 🛠️ **Użycie CLI Builder**

### **Podstawowe komendy:**

```bash
# Przetworzenie pojedynczego pliku
python builder.py faktura.pdf

# Przetworzenie wielu plików
python builder.py *.pdf *.jpg --output faktury-2025.html

# Przetworzenie całego katalogu
python builder.py --directory ./faktury --recursive

# Przetworzenie z custom tytułem
python builder.py --directory ./dokumenty --title "Archiwum firmowe 2025"

# Tryb verbose (szczegóły)
python builder.py *.* --verbose --output raport.html
```

### **Zaawansowane opcje:**

```bash
# Wyłączenie OCR (szybsze przetwarzanie)
python builder.py *.pdf --no-ocr

# Limit rozmiaru plików (w MB)
python builder.py --directory ./duze-pliki --max-size 50

# Custom katalog wyjściowy
python builder.py *.* --output-dir ./raporty --output miesięczny.html

# Przetwarzanie tylko obrazów
python builder.py --directory ./zdjecia --recursive | grep "\.jpg\|\.png"
```

---

## 💡 **Przykłady zastosowań**

### **1. Archiwizacja faktur**

```bash
# Struktura katalogu:
# faktury/
# ├── 2025-01/
# │   ├── faktura-001.pdf
# │   └── faktura-002.pdf
# └── 2025-02/
#     └── faktura-003.pdf

python builder.py --directory ./faktury --recursive \
  --title "Faktury 2025" \
  --output faktury-archiwum.html \
  --verbose

# Wynik: faktury-archiwum.html z OCR wszystkich faktur
```

### **2. Analiza nagrań CCTV**

```bash
# Przetwarzanie nagrań z kamer
python builder.py monitoring-*.mp4 \
  --title "Analiza CCTV - 20.06.2025" \
  --output monitoring-raport.html

# Wynik: klatki co 10s z każdego video + OCR tekstu z obrazu
```

### **3. Konwersja prezentacji PowerPoint**

```bash
# 1. Eksport PPT do PDF (ręcznie)
# 2. Konwersja PDF do MetaDoc
python builder.py prezentacja.pdf \
  --title "Prezentacja Q1 2025" \
  --output prezentacja-interaktywna.html

# Wynik: każdy slajd jako obraz + OCR tekstu
```

### **4. Archiwum dokumentów email**

```bash
# Struktura z załącznikami email:
# email-attachments/
# ├── umowa-najmu.pdf
# ├── faktura-prąd.jpg
# ├── zaświadczenie.png
# └── tabela-kosztów.xlsx

python builder.py --directory ./email-attachments \
  --title "Dokumenty z email - czerwiec 2025" \
  --output email-archiwum.html
```

---

## 🔧 **Konfiguracja zaawansowana**

### **1. Optymalizacja OCR dla języka polskiego**

```bash
# Instalacja dodatkowych pakietów językowych
sudo apt-get install tesseract-ocr-pol tesseract-ocr-eng

# Test OCR
tesseract --list-langs
# Powinno pokazać: pol, eng
```

### **2. Konfiguracja dla dużych plików**

Edytuj `builder.py` - sekcja limits:

```python
# Limity wydajnościowe
MAX_PDF_PAGES = 50          # Maksymalnie stron PDF
MAX_VIDEO_DURATION = 600    # Maksymalnie sekund video
MAX_IMAGE_SIZE = 20         # Maksymalnie MB na obraz
MAX_OCR_IMAGES = 100        # Maksymalnie obrazów do OCR
```

### **3. Custom template HTML**

Utwórz `templates/custom_template.html`:

```html
<!DOCTYPE html>
<html>
<head>
    <title>{{TITLE}}</title>
    <style>
        /* Twoje style CSS */
        body { background: linear-gradient(45deg, #667eea, #764ba2); }
    </style>
</head>
<body>
    <div class="custom-container">
        {{CONTENT}}
    </div>
    <script>
        // Twój custom JavaScript
    </script>
</body>
</html>
```

---

## 📊 **Monitoring wydajności**

### **1. Benchmark różnych typów plików**

```bash
# Test wydajności
time python builder.py --directory ./test-files --verbose

# Przykładowe wyniki:
# - Obrazy (10 plików, 50MB): ~30s
# - PDF (5 plików, 20 stron): ~45s  
# - Video (2 pliki, 5 min): ~60s
# - Excel (3 pliki): ~10s
```

### **2. Optymalizacja pamięci**

```bash
# Monitorowanie użycia pamięci
python -c "
import psutil
import os
process = psutil.Process(os.getpid())
print(f'RAM: {process.memory_info().rss / 1024 / 1024:.1f} MB')
"
```

---

## 🎯 **Integracja z workflow**

### **1. Automatyzacja z cron (Linux/macOS)**

```bash
# Edycja crontab
crontab -e

# Dodaj linię (codziennie o 2:00)
0 2 * * * cd /path/to/metadoc && python builder.py --directory /inbox --output daily-$(date +%Y%m%d).html
```

### **2.