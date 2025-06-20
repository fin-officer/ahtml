#!/usr/bin/env python3
"""
MetaDoc Builder - Advanced Compression Edition
Implementuje techniki eliminacji 33% overhead Base64:
- Compress-then-encode patterns
- Alternative encodings (Z85, Base91)
- Streaming compression
- Hybrid optimization strategies
"""

import os
import json
import base64
import gzip
import zlib
import brotli
import time
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import argparse

# Advanced compression imports
try:
    import lz4.frame as lz4

    LZ4_SUPPORT = True
except ImportError:
    LZ4_SUPPORT = False

try:
    import zstandard as zstd

    ZSTD_SUPPORT = True
except ImportError:
    ZSTD_SUPPORT = False

# Existing imports for file processing
try:
    from pdf2image import convert_from_path

    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

try:
    from PIL import Image, ImageOps

    PIL_SUPPORT = True
except ImportError:
    PIL_SUPPORT = False

try:
    import pytesseract

    OCR_SUPPORT = True
except ImportError:
    OCR_SUPPORT = False


class AdvancedCompressionEngine:
    """
    Zaawansowany silnik kompresji implementujący multiple strategie
    optymalizacji Base64 według research best practices
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.compression_stats = {
            'files_processed': 0,
            'total_original_size': 0,
            'total_compressed_size': 0,
            'total_processing_time': 0,
            'method_usage': {}
        }

        # Initialize available compression methods
        self.available_methods = self._detect_available_methods()
        self._log(f"Available compression methods: {list(self.available_methods.keys())}")

    def _detect_available_methods(self) -> Dict[str, bool]:
        """Wykrywa dostępne metody kompresji"""
        return {
            'gzip_base64': True,  # Always available
            'deflate_base64': True,  # zlib always available
            'brotli_base64': 'brotli' in globals(),
            'lz4_base64': LZ4_SUPPORT,
            'zstd_base64': ZSTD_SUPPORT,
            'z85': True,  # Custom implementation
            'base91': True,  # Custom implementation
            'streaming_gzip': True,
            'hybrid': True
        }

    def determine_optimal_method(self, data: bytes, file_type: str = 'unknown') -> str:
        """
        Określa optymalną metodę kompresji na podstawie:
        - Rozmiaru danych
        - Typu pliku
        - Charakterystyki danych
        - Dostępnych algorytmów
        """
        size = len(data)

        # Decision matrix based on research findings

        # Large files (>10MB) - streaming for memory efficiency
        if size > 10 * 1024 * 1024:
            return 'streaming_gzip'

        # Already compressed data (images, video) - avoid double compression
        if file_type in ['image', 'video', 'audio'] and size > 100 * 1024:
            return 'z85'  # 25% better than Base64, no compression overhead

        # Text-heavy content - maximum compression
        if file_type in ['pdf', 'text', 'json', 'xml']:
            if ZSTD_SUPPORT and size > 1024 * 1024:  # >1MB
                return 'zstd_base64'  # Best compression for large text
            elif self.available_methods['brotli_base64']:
                return 'brotli_base64'  # 10-20% better than gzip
            else:
                return 'gzip_base64'  # Reliable fallback

        # Small files (<100KB) - prioritize speed
        if size < 100 * 1024:
            if LZ4_SUPPORT:
                return 'lz4_base64'  # Fastest compression
            else:
                return 'z85'  # Fast encoding, no compression

        # Medium files - balanced approach
        if size < 1024 * 1024:  # <1MB
            return 'gzip_base64'  # Good balance

        # Default fallback
        return 'hybrid'

    def compress_data(self, data: bytes, method: str = 'auto',
                      compression_level: int = 6) -> Tuple[str, Dict[str, Any]]:
        """
        Kompresuje dane używając określonej metody
        Returns: (compressed_string, metadata)
        """
        start_time = time.time()
        original_size = len(data)

        if method == 'auto':
            method = self.determine_optimal_method(data)

        self._log(f"Compressing {original_size} bytes using {method}")

        # Execute compression based on method
        try:
            if method == 'gzip_base64':
                compressed = self._gzip_then_base64(data, compression_level)
            elif method == 'deflate_base64':
                compressed = self._deflate_then_base64(data, compression_level)
            elif method == 'brotli_base64':
                compressed = self._brotli_then_base64(data, compression_level)
            elif method == 'lz4_base64':
                compressed = self._lz4_then_base64(data)
            elif method == 'zstd_base64':
                compressed = self._zstd_then_base64(data, compression_level)
            elif method == 'z85':
                compressed = self._encode_z85(data)
            elif method == 'base91':
                compressed = self._encode_base91(data)
            elif method == 'streaming_gzip':
                compressed = self._streaming_gzip_base64(data)
            elif method == 'hybrid':
                compressed = self._hybrid_compress(data)
            else:
                # Fallback to gzip+base64
                compressed = self._gzip_then_base64(data, compression_level)
                method = 'gzip_base64'

        except Exception as e:
            self._log(f"Compression failed with {method}: {e}")
            # Emergency fallback to Base64 only
            compressed = base64.b64encode(data).decode('ascii')
            method = 'base64_only'

        processing_time = (time.time() - start_time) * 1000  # ms
        compressed_size = len(compressed.encode('utf-8'))

        # Calculate metrics
        compression_ratio = 1 - (compressed_size / original_size)
        efficiency = compressed_size / original_size
        space_saved = original_size - compressed_size

        # Compare with traditional Base64
        base64_size = int(original_size * 1.33)  # 33% overhead
        improvement_vs_base64 = 1 - (compressed_size / base64_size)
        
        metadata = {
            'method': method,
            'original_size': original_size,
            'compressed_size': compressed_size,
            'compression_ratio': compression_ratio,
            'efficiency': efficiency,
            'space_saved': space_saved,
            'processing_time_ms': processing_time,
            'base64_improvement': improvement_vs_base64,
            'compression_level': compression_level if method.endswith('_base64') else None
        }
        
        # Update global stats
        self._update_stats(method, original_size, compressed_size, processing_time)
        
        return compressed, metadata
    
    def decompress_data(self, compressed_data: str, metadata: Dict[str, Any]) -> bytes:
        """Dekompresuje dane na podstawie metadanych"""
        method = metadata['method']
        
        try:
            if method == 'gzip_base64':
                return self._base64_then_gunzip(compressed_data)
            elif method == 'deflate_base64':
                return self._base64_then_inflate(compressed_data)
            elif method == 'brotli_base64':
                return self._base64_then_brotli_decompress(compressed_data)
            elif method == 'lz4_base64':
                return self._base64_then_lz4_decompress(compressed_data)
            elif method == 'zstd_base64':
                return self._base64_then_zstd_decompress(compressed_data)
            elif method == 'z85':
                return self._decode_z85(compressed_data)
            elif method == 'base91':
                return self._decode_base91(compressed_data)
            elif method == 'streaming_gzip':
                return self._streaming_gunzip_base64(compressed_data)
            elif method == 'base64_only':
                return base64.b64decode(compressed_data)
            else:
                raise ValueError(f"Unknown compression method: {method}")
                
        except Exception as e:
            self._log(f"Decompression failed: {e}")
            raise
    
    # Core compression implementations
    def _gzip_then_base64(self, data: bytes, level: int = 6) -> str:
        """Standard gzip compression followed by Base64 encoding"""
        compressed = gzip.compress(data, compresslevel=level)
        return base64.b64encode(compressed).decode('ascii')
    
    def _base64_then_gunzip(self, data: str) -> bytes:
        """Reverse: Base64 decode then gzip decompress"""
        compressed = base64.b64decode(data)
        return gzip.decompress(compressed)
    
    def _deflate_then_base64(self, data: bytes, level: int = 6) -> str:
        """Deflate compression (zlib) + Base64"""
        compressed = zlib.compress(data, level)
        return base64.b64encode(compressed).decode('ascii')
    
    def _base64_then_inflate(self, data: str) -> bytes:
        """Base64 decode + deflate decompress"""
        compressed = base64.b64decode(data)
        return zlib.decompress(compressed)
    
    def _brotli_then_base64(self, data: bytes, level: int = 6) -> str:
        """Brotli compression + Base64 (10-20% better than gzip)"""
        if not self.available_methods['brotli_base64']:
            return self._gzip_then_base64(data, level)
        
        compressed = brotli.compress(data, quality=level)
        return base64.b64encode(compressed).decode('ascii')
    
    def _base64_then_brotli_decompress(self, data: str) -> bytes:
        """Base64 decode + Brotli decompress"""
        compressed = base64.b64decode(data)
        return brotli.decompress(compressed)
    
    def _lz4_then_base64(self, data: bytes) -> str:
        """LZ4 compression + Base64 (fastest compression)"""
        if not LZ4_SUPPORT:
            return self._gzip_then_base64(data, 1)  # Fast gzip fallback
        
        compressed = lz4.compress(data)
        return base64.b64encode(compressed).decode('ascii')
    
    def _base64_then_lz4_decompress(self, data: str) -> bytes:
        """Base64 decode + LZ4 decompress"""
        compressed = base64.b64decode(data)
        return lz4.decompress(compressed)
    
    def _zstd_then_base64(self, data: bytes, level: int = 6) -> str:
        """Zstandard compression + Base64 (excellent compression)"""
        if not ZSTD_SUPPORT:
            return self._brotli_then_base64(data, level)
        
        cctx = zstd.ZstdCompressor(level=level)
        compressed = cctx.compress(data)
        return base64.b64encode(compressed).decode('ascii')
    
    def _base64_then_zstd_decompress(self, data: str) -> bytes:
        """Base64 decode + Zstandard decompress"""
        compressed = base64.b64decode(data)
        dctx = zstd.ZstdDecompressor()
        return dctx.decompress(compressed)
    
    def _encode_z85(self, data: bytes) -> str:
        """
        Z85 encoding - 25% better efficiency than Base64
        Implementation of ZeroMQ Z85 specification
        """
        # Z85 alphabet (programming-language safe)
        alphabet = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.-:+=^!/*?&<>()[]{}@%$#"
        
        # Pad data to multiple of 4 bytes
        padding = (4 - len(data) % 4) % 4
        data = data + b'\x00' * padding
        
        result = []
        for i in range(0, len(data), 4):
            # Convert 4 bytes to 32-bit integer
            chunk = data[i:i+4]
            value = int.from_bytes(chunk, byteorder='big')
            
            # Encode as 5 Z85 characters
            encoded = ""
            for _ in range(5):
                encoded = alphabet[value % 85] + encoded
                value //= 85
            result.append(encoded)
        
        encoded_str = ''.join(result)
        
        # Add metadata for padding
        return f"Z85:{padding}:{encoded_str}"
    
    def _decode_z85(self, data: str) -> bytes:
        """Z85 decoding"""
        if not data.startswith("Z85:"):
            raise ValueError("Invalid Z85 format")
        
        parts = data.split(":", 2)
        if len(parts) != 3:
            raise ValueError("Invalid Z85 format")
        
        padding = int(parts[1])
        encoded = parts[2]
        
        alphabet = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.-:+=^!/*?&<>()[]{}@%$#"
        char_map = {char: idx for idx, char in enumerate(alphabet)}
        
        result = []
        for i in range(0, len(encoded), 5):
            chunk = encoded[i:i+5]
            if len(chunk) != 5:
                break
                
            # Decode 5 characters to 32-bit integer
            value = 0
            for char in chunk:
                value = value * 85 + char_map[char]
            
            # Convert to 4 bytes
            bytes_chunk = value.to_bytes(4, byteorder='big')
            result.append(bytes_chunk)
        
        decoded = b''.join(result)
        
        # Remove padding
        if padding > 0:
            decoded = decoded[:-padding]
        
        return decoded
    
    def _encode_base91(self, data: bytes) -> str:
        """
        Base91 encoding - approximately 23% size reduction vs Base64
        Using 13-bit packet encoding for efficiency
        """
        # Base91 alphabet
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!#$%&()*+,./:;<=>?@[]^_`{|}~\""
        
        v = 0  # Bit accumulator
        b = 0  # Number of bits in accumulator
        output = []
        
        for byte in data:
            v |= (byte & 255) << b
            b += 8
            
            if b > 13:
                output.append(alphabet[v & 8191])  # 8191 = 2^13 - 1
                v >>= 13
                b -= 13
        
        if b > 0:
            output.append(alphabet[v & 8191])
        
        return f"B91:{''.join(output)}"
    
    def _decode_base91(self, data: str) -> bytes:
        """Base91 decoding"""
        if not data.startswith("B91:"):
            raise ValueError("Invalid Base91 format")
        
        encoded = data[4:]
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!#$%&()*+,./:;<=>?@[]^_`{|}~\""
        decode_table = {char: idx for idx, char in enumerate(alphabet)}
        
        v = 0
        b = 0
        output = []
        
        for char in encoded:
            if char not in decode_table:
                continue
            
            v |= decode_table[char] << b
            b += 13
            
            while b >= 8:
                output.append(v & 255)
                v >>= 8
                b -= 8
        
        return bytes(output)
    
    def _streaming_gzip_base64(self, data: bytes, chunk_size: int = 64*1024) -> str:
        """
        Streaming compression for large files
        Processes data in chunks to maintain constant memory usage
        """
        result_chunks = []
        
        # Process in chunks
        for i in range(0, len(data), chunk_size):
            chunk = data[i:i+chunk_size]
            compressed_chunk = gzip.compress(chunk, compresslevel=6)
            encoded_chunk = base64.b64encode(compressed_chunk).decode('ascii')
            result_chunks.append(encoded_chunk)
        
        # Combine with separator for later reconstruction
        return f"STREAM:{len(result_chunks)}:" + "|".join(result_chunks)
    
    def _streaming_gunzip_base64(self, data: str) -> bytes:
        """Streaming decompression"""
        if not data.startswith("STREAM:"):
            raise ValueError("Invalid streaming format")
        
        parts = data.split(":", 2)
        if len(parts) != 3:
            raise ValueError("Invalid streaming format")
        
        chunk_count = int(parts[1])
        chunks_data = parts[2]
        
        encoded_chunks = chunks_data.split("|")
        if len(encoded_chunks) != chunk_count:
            raise ValueError("Chunk count mismatch")
        
        result_chunks = []
        for encoded_chunk in encoded_chunks:
            compressed_chunk = base64.b64decode(encoded_chunk)
            decompressed_chunk = gzip.decompress(compressed_chunk)
            result_chunks.append(decompressed_chunk)
        
        return b''.join(result_chunks)
    
    def _hybrid_compress(self, data: bytes) -> str:
        """
        Hybrid compression: try multiple methods and select best result
        Implements intelligent method selection based on actual results
        """
        candidates = []
        
        # Try different methods and measure results
        methods_to_try = ['gzip_base64', 'deflate_base64']
        
        if self.available_methods['brotli_base64']:
            methods_to_try.append('brotli_base64')
        
        if LZ4_SUPPORT and len(data) < 1024*1024:  # LZ4 for smaller files
            methods_to_try.append('lz4_base64')
        
        if len(data) < 100*1024:  # Try Z85 for small files
            methods_to_try.append('z85')
        
        # Test each method
        for method in methods_to_try:
            try:
                start_time = time.time()
                
                if method == 'gzip_base64':
                    result = self._gzip_then_base64(data, 6)
                elif method == 'deflate_base64':
                    result = self._deflate_then_base64(data, 6)
                elif method == 'brotli_base64':
                    result = self._brotli_then_base64(data, 6)
                elif method == 'lz4_base64':
                    result = self._lz4_then_base64(data)
                elif method == 'z85':
                    result = self._encode_z85(data)
                else:
                    continue
                
                processing_time = time.time() - start_time
                size = len(result.encode('utf-8'))
                
                # Score based on size and speed (weighted towards size)
                score = 1 / (size * 0.8 + processing_time * 1000 * 0.2)
                
                candidates.append((method, result, size, score))
                
            except Exception as e:
                self._log(f"Hybrid test failed for {method}: {e}")
                continue
        
        if not candidates:
            # Fallback if all methods fail
            return base64.b64encode(data).decode('ascii')
        
        # Select best method (highest score)
        best_method, best_result, best_size, best_score = max(candidates, key=lambda x: x[3])
        
        self._log(f"Hybrid selected {best_method} (size: {best_size}, score: {best_score:.6f})")
        
        # Prefix result with method identifier for decompression
        return f"HYBRID:{best_method}:{best_result}"
    
    def _update_stats(self, method: str, original_size: int, compressed_size: int, processing_time: float):
        """Update global compression statistics"""
        self.compression_stats['files_processed'] += 1
        self.compression_stats['total_original_size'] += original_size
        self.compression_stats['total_compressed_size'] += compressed_size
        self.compression_stats['total_processing_time'] += processing_time
        
        if method not in self.compression_stats['method_usage']:
            self.compression_stats['method_usage'][method] = 0
        self.compression_stats['method_usage'][method] += 1
    
    def get_compression_report(self) -> Dict[str, Any]:
        """Generate comprehensive compression performance report"""
        stats = self.compression_stats.copy()
        
        if stats['total_original_size'] > 0:
            overall_ratio = 1 - (stats['total_compressed_size'] / stats['total_original_size'])
            space_saved = stats['total_original_size'] - stats['total_compressed_size']
            base64_size = int(stats['total_original_size'] * 1.33)
            improvement_vs_base64 = 1 - (stats['total_compressed_size'] / base64_size)
            avg_processing_speed = stats['total_original_size'] / (stats['total_processing_time'] / 1000) / (1024*1024)  # MB/s
            
            stats.update({
                'overall_compression_ratio': overall_ratio,
                'space_saved_bytes': space_saved,
                'space_saved_mb': space_saved / (1024*1024),
                'improvement_vs_base64': improvement_vs_base64,
                'avg_processing_speed_mbps': avg_processing_speed,
                'most_used_method': max(stats['method_usage'], key=stats['method_usage'].get) if stats['method_usage'] else None
            })
        
        return stats
    
    def _log(self, message: str):
        """Logging helper"""
        if self.verbose:
            print(f"[AdvancedCompression] {message}")


class MetaDocBuilderAdvanced:
    """
    Enhanced MetaDoc Builder with advanced compression capabilities
    """
    
    def __init__(self, output_dir: str = "output", compression_method: str = "auto", verbose: bool = False):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        self.compression_engine = AdvancedCompressionEngine(verbose=verbose)
        self.compression_method = compression_method
        self.verbose = verbose
        self.documents = []
        
    def process_file_with_compression(self, file_path: str) -> Dict[str, Any]:
        """Process file with advanced compression optimization"""
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        self._log(f"Processing with advanced compression: {file_path.name}")
        
        # Read file data
        with open(file_path, 'rb') as f:
            file_data = f.read()
        
        # Determine file type for optimal compression
        file_type = self._detect_file_type(file_path)
        
        # Apply advanced compression
        compressed_data, compression_metadata = self.compression_engine.compress_data(
            file_data, 
            method=self.compression_method,
            compression_level=6
        )
        
        # Create document metadata
        stat = file_path.stat()
        doc = {
            "id": self._generate_id(file_path),
            "filename": file_path.name,
            "original_size": len(file_data),
            "compressed_size": compression_metadata['compressed_size'],
            "file_type": file_type,
            "mime_type": self._guess_mime_type(file_path),
            "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "compression": compression_metadata,
            "data": compressed_data,
            "thumbnail": "",
            "ocr": "",
            "metadata": {
                "processing_notes": f"Compressed using {compression_metadata['method']}",
                "base64_improvement": f"{compression_metadata['base64_improvement']*100:.1f}%",
                "efficiency_gain": f"{(1-compression_metadata['efficiency'])*100:.1f}%"
            }
        }
        
        # Generate thumbnail for images
        if file_type == 'image' and PIL_SUPPORT:
            doc['thumbnail'] = self._create_optimized_thumbnail(file_data)
        
        # OCR for images and PDFs
        if (file_type in ['image', 'pdf']) and OCR_SUPPORT:
            doc['ocr'] = self._extract_text_ocr(file_data, file_type)
        
        return doc
    
    def _create_optimized_thumbnail(self, image_data: bytes) -> str:
        """Create highly optimized thumbnail using advanced compression"""
        try:
            from io import BytesIO
            
            # Load image
            img = Image.open(BytesIO(image_data))
            
            # Create thumbnail (max 150px)
            img.thumbnail((150, 150), Image.Resampling.LANCZOS)
            
            # Save as WebP with high compression
            output = BytesIO()
            img.save(output, format='WebP', quality=60, method=6)
            thumbnail_data = output.getvalue()
            
            # Apply additional compression to thumbnail
            compressed_thumb, _ = self.compression_engine.compress_data(
                thumbnail_data, 
                method='gzip_base64'
            )
            
            return f"COMPRESSED_THUMB:{compressed_thumb}"
            
        except Exception as e:
            self._log(f"Thumbnail creation failed: {e}")
            return ""
    
    def build_optimized_html(self, output_file: str = "metadoc-optimized.html", 
                           title: str = "MetaDoc - Advanced Compression") -> str:
        """Build HTML with advanced compression optimizations"""
        
        # Compression statistics
        compression_report = self.compression_engine.get_compression_report()
        
        # Metadata with compression info
        metadata = {
            "project_info": {
                "name": title,
                "version": "2.0.0-advanced",
                "created": datetime.now().isoformat(),
                "compression_engine": "Advanced Multi-Algorithm",
                "total_documents": len(self.documents),
                "compression_report": compression_report
            },
            "documents": self.documents,
            "compression_methods_used": list(compression_report.get('method_usage', {}).keys()),
            "performance_metrics": {
                "space_saved_mb": compression_report.get('space_saved_mb', 0),
                "overall_efficiency": compression_report.get('overall_compression_ratio', 0),
                "base64_improvement": compression_report.get('improvement_vs_base64', 0),
                "processing_speed_mbps": compression_report.get('avg_processing_speed_mbps', 0)
            }
        }
        
        # Generate HTML with embedded compression engine
        html_template = self._get_advanced_html_template()
        
        # Compress metadata itself
        metadata_json = json.dumps(metadata, ensure_ascii=False)
        compressed_metadata, metadata_compression = self.compression_engine.compress_data(
            metadata_json.encode('utf-8'),
            method='brotli_base64' if self.compression_engine.available_methods['brotli_base64'] else 'gzip_base64'
        )
        
        # Embed compressed metadata
        final_html = html_template.replace(
            '{{COMPRESSED_METADATA}}',
            compressed_metadata
        ).replace(
            '{{METADATA_METHOD}}',
            metadata_compression['method']
        ).replace(
            '{{TITLE}}',
            title
        ).replace(
            '{{COMPRESSION_STATS}}',
            json.dumps(compression_report, indent=2)
        )
        
        # Save file
        output_path = self.output_dir / output_file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(final_html)
        
        # Log results
        self._log(f"✅ Generated optimized HTML: {output_path}")
        self._log(f"📊 Total documents: {len(self.documents)}")
        self._log(f"💾 Space saved: {compression_report.get('space_saved_mb', 0):.1f} MB")
        self._log(f"⚡ Base64 improvement: {compression_report.get('improvement_vs_base64', 0)*100:.1f}%")
        self._log(f"🚀 Processing speed: {compression_report.get('avg_processing_speed_mbps', 0):.1f} MB/s")
        
        return str(output_path)
    
    def _get_advanced_html_template(self) -> str:
        """HTML template with advanced compression support"""
        return '''<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{TITLE}}</title>
    <style>
        body { font-family: sans-serif; margin: 20px; background: linear-gradient(135deg, #667eea, #764ba2); color: white; }
        .container { max-width: 1200px; margin: 0 auto; background: rgba(255,255,255,0.95); color: #333; padding: 30px; border-radius: 12px; }
        .header { text-align: center; margin-bottom: 30px; }
        .compression-banner { background: #e8f4fd; border: 2px solid #007acc; border-radius: 8px; padding: 20px; margin-bottom: 30px; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }
        .stat-card { background: #f8f9fa; border-radius: 8px; padding: 15px; text-align: center; border-left: 4px solid #28a745; }
        .stat-value { font-size: 1.5rem; font-weight: bold; color: #007acc; }
        .doc-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; }
        .doc-card { border: 1px solid #ddd; border-radius: 8px; padding: 15px; background: #fafafa; }
        .doc-title { font-weight: bold; margin-bottom: 10px; }
        .compression-info { background: #e8f4fd; padding: 8px; border-radius: 4px; font-size: 0.9rem; margin: 10px 0; }
        .efficiency-bar { width: 100%; height: 8px; background: #e0e0e0; border-radius: 4px; overflow: hidden; margin: 5px 0; }
        .efficiency-fill { height: 100%; background: linear-gradient(90deg, #ff4444, #ffaa00, #44ff44); transition: width 0.3s ease; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📦 {{TITLE}}</h1>
            <p>Zaawansowana kompresja eliminująca 33% overhead Base64</p>
        </div>
        
        <div class="compression-banner">
            <h2>🚀 Osiągnięcia kompresji</h2>
            <div class="stats-grid" id="compressionStats">
                <!-- Stats will be populated by JavaScript -->
            </div>
        </div>
        
        <div class="doc-grid" id="documentsGrid">
            <!-- Documents will be populated by JavaScript -->
        </div>
    </div>
    
    <!-- Compressed metadata -->
    <script type="application/x-compressed-json" id="compressedMetadata" data-method="{{METADATA_METHOD}}">
    {{COMPRESSED_METADATA}}
    </script>
    
    <!-- Compression engine -->
    <script>
        class MetaDocDecompressor {
            constructor() {
                this.metadata = null;
                this.init();
            }
            
            async init() {
                await this.loadMetadata();
                this.renderStats();
                this.renderDocuments();
            }
            
            async loadMetadata() {
                const compressedElement = document.getElementById('compressedMetadata');
                const compressed = compressedElement.textContent.trim();
                const method = compressedElement.dataset.method;
                
                try {
                    // Decompress metadata based on method
                    let decompressed;
                    if (method.includes('gzip') || method.includes('deflate')) {
                        decompressed = await this.decompressGzipBase64(compressed);
                    } else if (method.includes('brotli')) {
                        decompressed = await this.decompressBrotliBase64(compressed);
                    } else {
                        // Fallback to direct JSON parse
                        decompressed = atob(compressed);
                    }
                    
                    this.metadata = JSON.parse(decompressed);
                    console.log('✅ Metadata successfully decompressed');
                } catch (error) {
                    console.error('❌ Metadata decompression failed:', error);
                    // Fallback handling
                }
            }
            
            async decompressGzipBase64(compressed) {
                // Browser-native decompression
                const compressedBytes = Uint8Array.from(atob(compressed), c => c.charCodeAt(0));
                
                if ('DecompressionStream' in window) {
                    const stream = new DecompressionStream('gzip');
                    const decompressedStream = new Response(compressedBytes).body.pipeThrough(stream);
                    const decompressedArrayBuffer = await new Response(decompressedStream).arrayBuffer();
                    return new TextDecoder().decode(decompressedArrayBuffer);
                } else {
                    // Fallback for older browsers
                    return atob(compressed);
                }
            }
            
            renderStats() {
                const statsContainer = document.getElementById('compressionStats');
                const report = this.metadata?.project_info?.compression_report || {};
                const metrics = this.metadata?.performance_metrics || {};
                
                statsContainer.innerHTML = `
                    <div class="stat-card">
                        <div class="stat-value">${report.files_processed || 0}</div>
                        <div>Plików przetworzonych</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${(metrics.space_saved_mb || 0).toFixed(1)} MB</div>
                        <div>Zaoszczędzone miejsce</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${(metrics.overall_efficiency * 100 || 0).toFixed(1)}%</div>
                        <div>Skuteczność kompresji</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${(metrics.base64_improvement * 100 || 0).toFixed(1)}%</div>
                        <div>Poprawa vs Base64</div>
                    </div>
                `;
            }
            
            renderDocuments() {
                const grid = document.getElementById('documentsGrid');
                const documents = this.metadata?.documents || [];
                
                grid.innerHTML = documents.map(doc => `
                    <div class="doc-card">
                        <div class="doc-title">${doc.filename}</div>
                        
                        <div class="compression-info">
                            <strong>Metoda:</strong> ${doc.compression?.method || 'N/A'}<br>
                            <strong>Kompresja:</strong> ${((doc.compression?.compression_ratio || 0) * 100).toFixed(1)}%<br>
                            <strong>Oszczędność:</strong> ${this.formatBytes(doc.compression?.space_saved || 0)}
                        </div>
                        
                        <div>
                            <strong>Efektywność:</strong>
