"""
Import Node
===========
Handles file parsing for document imports (PDF, Docx, TXT).
Uses unstructured library for extraction.
"""

import logging
from typing import BinaryIO

from ..config import BacklogAgentConfig

logger = logging.getLogger(__name__)

class ImportNode:
    """Parses uploaded files into text."""
    
    def __init__(self, config: BacklogAgentConfig | None = None):
        self.config = config or BacklogAgentConfig()
        
    def parse_file(self, file: BinaryIO, filename: str) -> str:
        """
        Parse file content into string.
        
        Args:
            file: File-like object
            filename: Name of the file (for extension detection)
            
        Returns:
            Extracted text content
        """
        try:
            logger.info(f"ImportNode: Parsing file '{filename}'")
            
            ext = filename.lower().split('.')[-1] if '.' in filename else ""
            
            if ext in ['txt', 'md', 'log']:
                from unstructured.partition.text import partition_text
                elements = partition_text(file=file)
            elif ext == 'docx':
                 from unstructured.partition.docx import partition_docx
                 elements = partition_docx(file=file)
            elif ext == 'pdf':
                 from unstructured.partition.pdf import partition_pdf
                 elements = partition_pdf(file=file)
            else:
                # Fallback to auto
                from unstructured.partition.auto import partition
                elements = partition(file=file, metadata_filename=filename, include_page_breaks=False)
                
            text = "\n\n".join([str(e) for e in elements])
            
            logger.info(f"ImportNode: Extracted {len(text)} chars from '{filename}'")
            return text
            
        except ImportError as e:
            logger.error(f"ImportNode: Missing specific parser - {e}")
            return f"Error: Missing parser library for .{ext}: {str(e)}"
        except Exception as e:
            logger.error("ImportNode: unstructured library not found")
            return "Error: Server missing document parsing libraries."
        except Exception as e:
            logger.error(f"ImportNode: Failed to parse file - {e}")
            return f"Error parsing file: {str(e)}"
