"""PDF document loader."""

from typing import List, Dict, Any, Optional
from agent_sdk.data_connectors.document import Document
import os


class PDFLoader:
    """Extract text and metadata from PDF files."""
    
    def __init__(self, extract_tables: bool = False):
        """Initialize PDF loader.
        
        Args:
            extract_tables: Whether to attempt table extraction.
        """
        self.extract_tables = extract_tables
        self._pdfplumber_available = self._check_pdfplumber()
    
    @staticmethod
    def _check_pdfplumber() -> bool:
        """Check if pdfplumber is available.
        
        Returns:
            True if pdfplumber is installed.
        """
        try:
            import pdfplumber
            return True
        except ImportError:
            return False
    
    def load(self, file_path: str) -> List[Document]:
        """Load and parse PDF file.
        
        Args:
            file_path: Path to PDF file.
            
        Returns:
            List of Document objects, one per page.
            
        Raises:
            FileNotFoundError: If file doesn't exist.
            ValueError: If file is not a valid PDF.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF file not found: {file_path}")
        
        if not file_path.lower().endswith('.pdf'):
            raise ValueError(f"File is not a PDF: {file_path}")
        
        documents = []
        
        try:
            import pdfplumber
        except ImportError:
            # Fallback: return basic document with file info
            return self._fallback_load(file_path)
        
        try:
            with pdfplumber.open(file_path) as pdf:
                metadata = self.extract_metadata(file_path)
                
                for page_num, page in enumerate(pdf.pages, 1):
                    # Extract text
                    text = page.extract_text() or ""
                    
                    # Extract tables if requested
                    tables = []
                    if self.extract_tables:
                        try:
                            tables = page.extract_tables() or []
                        except Exception:
                            pass
                    
                    # Create document for page
                    doc_metadata = {
                        **metadata,
                        "page_number": page_num,
                        "page_width": page.width,
                        "page_height": page.height,
                        "tables": len(tables),
                    }
                    
                    document = Document(
                        content=text,
                        metadata=doc_metadata,
                        source=file_path,
                        doc_id=f"{os.path.basename(file_path)}_{page_num}",
                    )
                    documents.append(document)
        
        except Exception as e:
            raise ValueError(f"Error parsing PDF: {str(e)}")
        
        return documents
    
    def extract_metadata(self, file_path: str) -> Dict[str, Any]:
        """Extract PDF metadata.
        
        Args:
            file_path: Path to PDF file.
            
        Returns:
            Dictionary of metadata.
        """
        metadata = {
            "file_name": os.path.basename(file_path),
            "file_size": os.path.getsize(file_path),
        }
        
        try:
            import pdfplumber
            
            with pdfplumber.open(file_path) as pdf:
                # Extract PDF metadata
                pdf_meta = pdf.metadata or {}
                metadata.update({
                    "total_pages": len(pdf.pages),
                    "title": pdf_meta.get("Title", ""),
                    "author": pdf_meta.get("Author", ""),
                    "subject": pdf_meta.get("Subject", ""),
                })
        except Exception:
            metadata["total_pages"] = "unknown"
        
        return metadata
    
    def _fallback_load(self, file_path: str) -> List[Document]:
        """Fallback loader when pdfplumber not available.
        
        Args:
            file_path: Path to PDF file.
            
        Returns:
            List with single document containing file info.
        """
        document = Document(
            content=f"[PDF file: {os.path.basename(file_path)}] - Install pdfplumber for content extraction",
            metadata={
                "file_name": os.path.basename(file_path),
                "file_size": os.path.getsize(file_path),
                "note": "pdfplumber not installed",
            },
            source=file_path,
        )
        return [document]
