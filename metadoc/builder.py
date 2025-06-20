#!/usr/bin/env python3
"""
MetaDoc Builder - CLI Tool
Konwertuje PDF, obrazy, video, XLS do samowystarczalnego HTML z metadanymi
"""

import os
import json
import base64
import argparse
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import mimetypes

# Importy opcjonalne - graceful degradation
try:
    from pdf2image import convert_from_path

    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    print("⚠️  pdf2image nie zainstalowane - brak obsługi PDF")

try:
    from PIL import Image, ImageOps

    PIL_SUPPORT = True
except ImportError:
    PIL_SUPPORT = False
    print("⚠️  Pillow nie zainstalowane - ograniczona obsługa obrazów")

try:
    import pytesseract

    OCR_SUPPORT = True
except ImportError:
    OCR_SUPPORT = False
    print("⚠️  pytesseract nie zainstalowany - brak OCR")

try:
    import pandas as pd

    EXCEL_SUPPORT = True
except ImportError:
    EXCEL_SUPPORT = False
    print("⚠️  pandas nie zainstalowany - brak obsługi Excel")

try:
    import cv2

    VIDEO_SUPPORT = True
except ImportError:
    VIDEO_SUPPORT = False
    print("⚠️  opencv-python nie zainstalowany - brak obsługi video")


class MetaDocBuilder:
    """Główna klasa do budowania dokumentów MetaDoc"""

    def __init__(self, output_dir: str = "output", verbose: bool = False):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.verbose = verbose
        self.documents = []

    def log(self, message: str) -> None:
        """Logowanie wiadomości"""
        if self.verbose:
            print(f"[MetaDoc] {message}")

    def process_file(self, file_path: str) -> Dict[str, Any]:
        """Przetwarza pojedynczy plik"""
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"Plik nie istnieje: {file_path}")

        self.log(f"Przetwarzanie: {file_path.name}")

        # Podstawowe metadane
        stat = file_path.stat()
        doc = {
            "id": self._generate_id(file_path),
            "filename": file_path.name,
            "size": stat.st_size,
            "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "type": self._detect_file_type(file_path),
            "mime_type": mimetypes.guess_type(str(file_path))[0] or "application/octet-stream",
            "thumbnail": "",
            "full_image": "",
            "ocr": "",
            "metadata": {
                "confidence": 0.0,
                "entities": [],
                "analysis": "",
                "pages": 1
            },
            "tags": []
        }

        # Specjalizowane przetwarzanie na podstawie typu
        if doc["type"] == "image":
            self._process_image(file_path, doc)
        elif doc["type"] == "pdf":
            self._process_pdf(file_path, doc)
        elif doc["type"] == "video":
            self._process_video(file_path, doc)
        elif doc["type"] == "spreadsheet":
            self._process_spreadsheet(file_path, doc)
        else:
            self._process_generic(file_path, doc)

        return doc

    def _generate_id(self, file_path: Path) -> str:
        """Generuje unikalny ID dla pliku"""
        content = f"{file_path.name}{file_path.stat().st_size}{file_path.stat().st_mtime}"
        return hashlib.md5(content.encode()).hexdigest()[:12]

    def _detect_file_type(self, file_path: Path) -> str:
        """Wykrywa typ pliku"""
        ext = file_path.suffix.lower()

        if ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tiff']:
            return "image"
        elif ext == '.pdf':
            return "pdf"
        elif ext in ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv']:
            return "video"
        elif ext in ['.xls', '.xlsx', '.csv']:
            return "spreadsheet"
        elif ext in ['.txt', '.md', '.rtf']:
            return "text"
        else:
            return "other"

    def _process_image(self, file_path: Path, doc: Dict[str, Any]) -> None:
        """Przetwarza plik obrazu"""
        if not PIL_SUPPORT:
            doc["thumbnail"] = self._create_placeholder_thumbnail("🖼️", "Image")
            return

        try:
            # Wczytanie obrazu
            with Image.open(file_path) as img:
                # Metadane obrazu
                doc["metadata"]["width"] = img.width
                doc["metadata"]["height"] = img.height
                doc["metadata"]["mode"] = img.mode

                # EXIF jeśli dostępne
                if hasattr(img, '_getexif') and img._getexif():
                    doc["metadata"]["exif"] = dict(img._getexif())

                # Tworzenie miniaturki
                doc["thumbnail"] = self._create_image_thumbnail(img)

                # Pełny obraz jako Data URI (jeśli mały)
                if doc["size"] < 5 * 1024 * 1024:  # 5MB limit
                    doc["full_image"] = self._image_to_data_uri(img, file_path.suffix)

                # OCR jeśli dostępne
                if OCR_SUPPORT:
                    try:
                        ocr_text = pytesseract.image_to_string(img, lang='pol')
                        doc["ocr"] = ocr_text.strip()
                        doc["metadata"]["confidence"] = 0.8  # Założenie
                        doc["metadata"]["analysis"] = self._analyze_text(ocr_text)
                        doc["tags"] = self._extract_tags(ocr_text)
                    except Exception as e:
                        self.log(f"Błąd OCR: {e}")

        except Exception as e:
            self.log(f"Błąd przetwarzania obrazu {file_path}: {e}")
            doc["thumbnail"] = self._create_placeholder_thumbnail("❌", "Error")

    def _process_pdf(self, file_path: Path, doc: Dict[str, Any]) -> None:
        """Przetwarza plik PDF"""
        if not PDF_SUPPORT:
            doc["thumbnail"] = self._create_placeholder_thumbnail("📄", "PDF")
            doc["ocr"] = "PDF - wymagana instalacja pdf2image"
            return

        try:
            # Konwersja pierwszej strony do obrazu
            images = convert_from_path(file_path, first_page=1, last_page=1, dpi=150)

            if images:
                first_page = images[0]
                doc["thumbnail"] = self._create_image_thumbnail(first_page)
                doc["metadata"]["pages"] = len(convert_from_path(file_path, dpi=150))

                # OCR pierwszej strony
                if OCR_SUPPORT:
                    try:
                        ocr_text = pytesseract.image_to_string(first_page, lang='pol')
                        doc["ocr"] = ocr_text.strip()
                        doc["metadata"]["analysis"] = self._analyze_text(ocr_text)
                        doc["tags"] = self._extract_tags(ocr_text)
                    except Exception as e:
                        self.log(f"Błąd OCR PDF: {e}")

                # Zapisanie wszystkich stron jako obrazy (opcjonalnie)
                if doc["metadata"]["pages"] <= 10:  # Limit dla małych PDF-ów
                    all_pages = convert_from_path(file_path, dpi=150)
                    doc["metadata"]["page_images"] = []

                    for i, page_img in enumerate(all_pages):
                        page_data_uri = self._create_image_thumbnail(page_img, size=400)
                        doc["metadata"]["page_images"].append({
                            "page": i + 1,
                            "thumbnail": page_data_uri
                        })

        except Exception as e:
            self.log(f"Błąd przetwarzania PDF {file_path}: {e}")
            doc["thumbnail"] = self._create_placeholder_thumbnail("❌", "PDF Error")

    def _process_video(self, file_path: Path, doc: Dict[str, Any]) -> None:
        """Przetwarza plik video"""
        if not VIDEO_SUPPORT:
            doc["thumbnail"] = self._create_placeholder_thumbnail("🎥", "Video")
            doc["ocr"] = "Video - wymagana instalacja opencv-python"
            return

        try:
            cap = cv2.VideoCapture(str(file_path))

            # Metadane video
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = frame_count / fps if fps > 0 else 0

            doc["metadata"]["fps"] = fps
            doc["metadata"]["frame_count"] = frame_count
            doc["metadata"]["duration"] = duration
            doc["metadata"]["width"] = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            doc["metadata"]["height"] = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            # Ekstrakcja pierwszej klatki jako miniaturka
            ret, frame = cap.read()
            if ret:
                # Konwersja BGR do RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_image = Image.fromarray(frame_rgb)
                doc["thumbnail"] = self._create_image_thumbnail(pil_image)

                # OCR pierwszej klatki
                if OCR_SUPPORT:
                    try:
                        ocr_text = pytesseract.image_to_string(pil_image, lang='pol')
                        doc["ocr"] = f"Pierwsza klatka: {ocr_text.strip()}"
                        doc["tags"] = self._extract_tags(ocr_text)
                    except Exception as e:
                        self.log(f"Błąd OCR video: {e}")

                # Ekstrakcja klatek co N sekund (dla krótkich filmów)
                if duration <= 300:  # 5 minut
                    doc["metadata"]["key_frames"] = self._extract_key_frames(cap, fps, duration)

            cap.release()

        except Exception as e:
            self.log(f"Błąd przetwarzania video {file_path}: {e}")
            doc["thumbnail"] = self._create_placeholder_thumbnail("❌", "Video Error")

    def _process_spreadsheet(self, file_path: Path, doc: Dict[str, Any]) -> None:
        """Przetwarza arkusz kalkulacyjny"""
        if not EXCEL_SUPPORT:
            doc["thumbnail"] = self._create_placeholder_thumbnail("📊", "Excel")
            doc["ocr"] = "Excel - wymagana instalacja pandas"
            return

        try:
            # Wczytanie arkusza
            if file_path.suffix.lower() == '.csv':
                df = pd.read_csv(file_path)
                sheets = {'Sheet1': df}
            else:
                excel_file = pd.ExcelFile(file_path)
                sheets = {sheet: excel_file.parse(sheet) for sheet in excel_file.sheet_names}

            doc["metadata"]["sheets"] = list(sheets.keys())
            doc["metadata"]["total_rows"] = sum(len(df) for df in sheets.values())
            doc["metadata"]["total_columns"] = sum(len(df.columns) for df in sheets.values())

            # Konwersja do HTML
            html_tables = []
            text_content = []

            for sheet_name, df in sheets.items():
                if len(df) > 0:
                    # Podgląd pierwszych 10 wierszy
                    preview_df = df.head(10)
                    html_table = preview_df.to_html(classes='excel-table', table_id=f'table-{sheet_name}')
                    html_tables.append(f"<h3>{sheet_name}</h3>{html_table}")

                    # Tekst do analizy
                    text_content.extend(df.astype(str).values.flatten().tolist())

            doc["metadata"]["html_preview"] = "\n".join(html_tables)
            doc["ocr"] = " ".join(text_content[:1000])  # Pierwsze 1000 komórek
            doc["metadata"]["analysis"] = self._analyze_text(doc["ocr"])
            doc["tags"] = self._extract_tags(doc["ocr"]) + ["excel", "tabela"]

            # Tworzenie miniaturki z pierwszej tabeli
            doc["thumbnail"] = self._create_placeholder_thumbnail("📊", f"{len(sheets)} arkuszy")

        except Exception as e:
            self.log(f"Błąd przetwarzania Excel {file_path}: {e}")
            doc["thumbnail"] = self._create_placeholder_thumbnail("❌", "Excel Error")

    def _process_generic(self, file_path: Path, doc: Dict[str, Any]) -> None:
        """Przetwarza pliki ogólne"""
        doc["thumbnail"] = self._create_placeholder_thumbnail("📎", doc["type"].upper())

        # Próba wczytania jako tekst
        try:
            if doc["size"] < 1024 * 1024:  # 1MB limit dla tekstów
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    doc["ocr"] = content[:5000]  # Pierwsze 5000 znaków
                    doc["metadata"]["analysis"] = self._analyze_text(content)
                    doc["tags"] = self._extract_tags(content)
        except Exception as e:
            self.log(f"Nie można wczytać jako tekst: {e}")

    def _create_image_thumbnail(self, img: Image.Image, size: int = 200) -> str:
        """Tworzy miniaturkę obrazu jako Data URI"""
        try:
            # Tworzenie miniaturki zachowującej proporcje
            img_copy = img.copy()
            img_copy.thumbnail((size, size), Image.Resampling.LANCZOS)

            # Konwersja do WebP
            import io
            buffer = io.BytesIO()
            img_copy.save(buffer, format='WebP', quality=70)
            img_data = buffer.getvalue()

            # Kodowanie Base64
            b64_data = base64.b64encode(img_data).decode('utf-8')
            return f"data:image/webp;base64,{b64_data}"

        except Exception as e:
            self.log(f"Błąd tworzenia miniaturki: {e}")
            return self._create_placeholder_thumbnail("🖼️", "Image")

    def _image_to_data_uri(self, img: Image.Image, ext: str) -> str:
        """Konwertuje obraz do Data URI"""
        try:
            import io
            buffer = io.BytesIO()

            # Wybór formatu na podstawie rozszerzenia
            format_map = {
                '.jpg': 'JPEG', '.jpeg': 'JPEG',
                '.png': 'PNG', '.webp': 'WebP',
                '.gif': 'GIF', '.bmp': 'BMP'
            }

            img_format = format_map.get(ext.lower(), 'JPEG')
            mime_type = f"image/{img_format.lower()}"

            img.save(buffer, format=img_format, quality=85)
            img_data = buffer.getvalue()

            b64_data = base64.b64encode(img_data).decode('utf-8')
            return f"data:{mime_type};base64,{b64_data}"

        except Exception as e:
            self.log(f"Błąd konwersji do Data URI: {e}")
            return ""

    def _create_placeholder_thumbnail(self, icon: str, text: str) -> str:
        """Tworzy placeholder miniaturkę SVG"""
        svg = f'''<svg width="200" height="200" xmlns="http://www.w3.org/2000/svg">
            <rect width="200" height="200" fill="#f0f0f0"/>
            <text x="100" y="80" text-anchor="middle" font-family="sans-serif" font-size="48">{icon}</text>
            <text x="100" y="130" text-anchor="middle" font-family="sans-serif" font-size="16" fill="#666">{text}</text>
        </svg>'''

        b64_svg = base64.b64encode(svg.encode('utf-8')).decode('utf-8')
        return f"data:image/svg+xml;base64,{b64_svg}"

    def _extract_key_frames(self, cap, fps: float, duration: float, interval: int = 10) -> List[Dict]:
        """Ekstraktuje kluczowe klatki z video co N sekund"""
        key_frames = []

        try:
            for second in range(0, int(duration), interval):
                frame_number = int(second * fps)
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)

                ret, frame = cap.read()
                if ret:
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    pil_image = Image.fromarray(frame_rgb)
                    thumbnail = self._create_image_thumbnail(pil_image, size=150)

                    key_frames.append({
                        "timestamp": second,
                        "frame_number": frame_number,
                        "thumbnail": thumbnail
                    })

                    if len(key_frames) >= 20:  # Limit klatek
                        break

        except Exception as e:
            self.log(f"Błąd ekstraktacji klatek: {e}")

        return key_frames

    def _analyze_text(self, text: str) -> str:
        """Analizuje tekst i zwraca insights"""
        if not text or not text.strip():
            return "Brak tekstu do analizy"

        lines = [line.strip() for line in text.split('\n') if line.strip()]
        words = text.split()

        analysis = f"Znaleziono {len(lines)} linii i {len(words)} słów. "

        # Wykrywanie wzorców
        import re

        dates = re.findall(r'\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}', text)
        amounts = re.findall(r'\d+[,\.]\d{2}(?:\s*(?:zł|PLN|EUR|USD))?', text)
        emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
        phones = re.findall(r'(?:\+48\s?)?(?:\d{3}[-\s]?\d{3}[-\s]?\d{3}|\d{2}[-\s]?\d{3}[-\s]?\d{2}[-\s]?\d{2})', text)

        if dates:
            analysis += f"Wykryto {len(dates)} dat. "
        if amounts:
            analysis += f"Wykryto {len(amounts)} kwot pieniężnych. "
        if emails:
            analysis += f"Wykryto {len(emails)} adresów email. "
        if phones:
            analysis += f"Wykryto {len(phones)} numerów telefonu. "

        # Wykrywanie typów dokumentów
        text_lower = text.lower()
        if any(word in text_lower for word in ['faktura', 'invoice', 'rachun']):
            analysis += "Prawdopodobnie faktura. "
        if any(word in text_lower for word in ['umowa', 'contract', 'agreement']):
            analysis += "Prawdopodobnie umowa. "
        if any(word in text_lower for word in ['raport', 'report', 'sprawozdanie']):
            analysis += "Prawdopodobnie raport. "

        return analysis

    def _extract_tags(self, text: str) -> List[str]:
        """Ekstraktuje tagi z tekstu"""
        if not text:
            return []

        tags = []
        text_lower = text.lower()

        # Mapowanie słów kluczowych na tagi
        tag_keywords = {
            'faktura': ['faktura', 'invoice', 'rachun'],
            'umowa': ['umowa', 'contract', 'agreement'],
            'raport': ['raport', 'report', 'sprawozdanie'],
            'finansowe': ['pln', 'eur', 'usd', 'kwota', 'suma', 'koszt'],
            'data': [r'\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}'],
            'email': [r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'],
            'telefon': [r'(?:\+48\s?)?(?:\d{3}[-\s]?\d{3}[-\s]?\d{3})'],
            'adres': ['ulica', 'ul.', 'street', 'kod pocztowy', 'miasto']
        }

        import re
        for tag, keywords in tag_keywords.items():
            for keyword in keywords:
                if keyword.startswith(r'\d') or keyword.startswith(r'\b'):
                    # Regex pattern
                    if re.search(keyword, text):
                        tags.append(tag)
                        break
                else:
                    # Zwykłe słowo
                    if keyword in text_lower:
                        tags.append(tag)
                        break

        return list(set(tags))  # Usuń duplikaty

    def build_html(self, output_file: str = "metadoc.html", title: str = "MetaDoc Container") -> str:
        """Buduje końcowy plik HTML z wszystkimi dokumentami"""

        # Przygotowanie metadanych
        metadata = {
            "project_info": {
                "name": title,
                "version": "1.0.0",
                "created": datetime.now().isoformat(),
                "generated_by": "MetaDoc Builder",
                "total_documents": len(self.documents),
                "total_size": sum(doc.get("size", 0) for doc in self.documents)
            },
            "documents": self.documents
        }

        # Wczytanie szablonu HTML
        template_html = self._get_html_template()

        # Wstawienie metadanych
        metadata_json = json.dumps(metadata, indent=2, ensure_ascii=False)
        final_html = template_html.replace(
            '{"project_info": {"name": "MetaDoc System"',
            f'{{"project_info": {{"name": "{title}"'
        ).replace(
            '"documents": []',
            f'"documents": {json.dumps(self.documents, indent=2, ensure_ascii=False)}'
        )

        # Zapisanie pliku
        output_path = self.output_dir / output_file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(final_html)

        self.log(f"✅ Wygenerowano: {output_path}")
        self.log(f"📊 Dokumentów: {len(self.documents)}")
        self.log(f"💾 Rozmiar: {self._format_size(sum(doc.get('size', 0) for doc in self.documents))}")

        return str(output_path)

    def _get_html_template(self) -> str:
        """Zwraca szablon HTML (uproszczony - w rzeczywistości wczytaj z pliku)"""
        # W rzeczywistej implementacji wczytaj z zewnętrznego pliku template.html
        return '''<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MetaDoc Container</title>
    <style>
        body { font-family: sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; }
        .header { text-align: center; margin-bottom: 30px; color: #333; }
        .doc-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; }
        .doc-card { border: 1px solid #ddd; border-radius: 8px; padding: 15px; background: #fafafa; }
        .doc-image { width: 100%; height: 150px; object-fit: cover; border-radius: 4px; }
        .doc-title { font-weight: bold; margin: 10px 0; }
        .doc-meta { font-size: 0.9rem; color: #666; margin: 5px 0; }
        .ocr-text { background: white; border: 1px solid #ddd; padding: 8px; font-family: monospace; font-size: 0.8rem; max-height: 100px; overflow-y: auto; }
        .tags { margin: 10px 0; }
        .tag { background: #007acc; color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; margin-right: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📦 MetaDoc Container</h1>
            <p>Wygenerowano automatycznie przez MetaDoc Builder</p>
        </div>
        <div class="doc-grid" id="docGrid"></div>
    </div>

    <script type="application/json" id="metadata">
    {"project_info": {"name": "MetaDoc System", "version": "1.0.0", "created": "2025-06-20", "description": "Inteligentny kontener danych z OCR i analizą AI"}, "documents": []}
    </script>

    <script>
        const data = JSON.parse(document.getElementById('metadata').textContent);
        const grid = document.getElementById('docGrid');

        data.documents.forEach(doc => {
            const card = document.createElement('div');
            card.className = 'doc-card';

            card.innerHTML = `
                <div class="doc-title">${doc.filename}</div>
                ${doc.thumbnail ? `<img class="doc-image" src="${doc.thumbnail}" alt="${doc.filename}">` : ''}
                <div class="doc-meta">Typ: ${doc.type} | Rozmiar: ${formatSize(doc.size)}</div>
                <div class="doc-meta">Utworzono: ${new Date(doc.created).toLocaleDateString('pl-PL')}</div>
                <div class="tags">${doc.tags.map(tag => `<span class="tag">${tag}</span>`).join('')}</div>
                ${doc.ocr ? `<div class="ocr-text">${doc.ocr.substring(0, 200)}${doc.ocr.length > 200 ? '...' : ''}</div>` : ''}
                <div style="font-size: 0.8rem; color: #888; margin-top: 10px;">${doc.metadata.analysis}</div>
            `;

            grid.appendChild(card);
        });

        function formatSize(bytes) {
            if (bytes === 0) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        }
    </script>
</body>
</html>'''

    def _format_size(self, bytes: int) -> str:
        """Formatuje rozmiar pliku"""
        if bytes == 0:
            return "0 B"

        k = 1024
        sizes = ['B', 'KB', 'MB', 'GB', 'TB']
        i = 0

        while bytes >= k and i < len(sizes) - 1:
            bytes /= k
            i += 1

        return f"{bytes:.1f} {sizes[i]}"

    def add_document(self, doc: Dict[str, Any]) -> None:
        """Dodaje dokument do kolekcji"""
        self.documents.append(doc)

    def process_directory(self, directory: str, recursive: bool = False) -> List[Dict[str, Any]]:
        """Przetwarza wszystkie pliki w katalogu"""
        directory = Path(directory)

        if not directory.exists():
            raise FileNotFoundError(f"Katalog nie istnieje: {directory}")

        pattern = "**/*" if recursive else "*"
        files = [f for f in directory.glob(pattern) if f.is_file()]

        processed_docs = []

        for file_path in files:
            try:
                doc = self.process_file(file_path)
                self.add_document(doc)
                processed_docs.append(doc)
            except Exception as e:
                self.log(f"❌ Błąd przetwarzania {file_path}: {e}")

        return processed_docs


def main():
    """Główna funkcja CLI"""
    parser = argparse.ArgumentParser(
        description="MetaDoc Builder - Konwerter plików do samowystarczalnego HTML",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Przykłady użycia:
  python builder.py file1.pdf file2.jpg --output raport.html
  python builder.py --directory ./documents --recursive --output wszystkie.html
  python builder.py *.pdf --title "Faktury 2025" --verbose
        """
    )

    # Argumenty wejściowe
    parser.add_argument('files', nargs='*', help='Pliki do przetworzenia')
    parser.add_argument('-d', '--directory', help='Katalog do przetworzenia')
    parser.add_argument('-r', '--recursive', action='store_true', help='Przetwarzaj rekurencyjnie')

    # Argumenty wyjściowe
    parser.add_argument('-o', '--output', default='metadoc.html', help='Nazwa pliku wyjściowego')
    parser.add_argument('--output-dir', default='output', help='Katalog wyjściowy')
    parser.add_argument('-t', '--title', default='MetaDoc Container', help='Tytuł dokumentu')

    # Opcje
    parser.add_argument('-v', '--verbose', action='store_true', help='Szczegółowe logowanie')
    parser.add_argument('--no-ocr', action='store_true', help='Wyłącz OCR')
    parser.add_argument('--max-size', type=int, default=10, help='Maksymalny rozmiar pliku w MB')

    args = parser.parse_args()

    # Walidacja argumentów
    if not args.files and not args.directory:
        parser.error("Podaj pliki lub katalog do przetworzenia")

    # Inicjalizacja buildera
    builder = MetaDocBuilder(output_dir=args.output_dir, verbose=args.verbose)

    # Globalne wyłączenie OCR jeśli wybrano
    if args.no_ocr:
        global OCR_SUPPORT
        OCR_SUPPORT = False
        builder.log("OCR wyłączony przez użytkownika")

    # Przetwarzanie plików
    total_processed = 0

    try:
        # Przetwarzanie pojedynczych plików
        if args.files:
            for file_path in args.files:
                file_path = Path(file_path)

                # Sprawdzenie rozmiaru
                if file_path.exists() and file_path.stat().st_size > args.max_size * 1024 * 1024:
                    builder.log(f"⚠️  Plik {file_path} przekracza limit rozmiaru ({args.max_size}MB)")
                    continue

                try:
                    doc = builder.process_file(file_path)
                    builder.add_document(doc)
                    total_processed += 1
                except Exception as e:
                    builder.log(f"❌ Błąd: {e}")

        # Przetwarzanie katalogu
        if args.directory:
            docs = builder.process_directory(args.directory, args.recursive)
            total_processed += len(docs)

        # Generowanie HTML
        if total_processed > 0:
            output_file = builder.build_html(args.output, args.title)
            print(f"✅ Sukces! Wygenerowano: {output_file}")
            print(f"📁 Przetworzono: {total_processed} plików")
        else:
            print("❌ Nie przetworzono żadnych plików")
            return 1

    except KeyboardInterrupt:
        print("\n⏹️  Przerwano przez użytkownika")
        return 1
    except Exception as e:
        print(f"❌ Błąd krytyczny: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())