"""CSV and JSON structured data loaders."""

from typing import List, Dict, Any, Optional
from agent_sdk.data_connectors.document import Document
import os
import json


class CSVLoader:
    """Load and parse CSV files."""
    
    def __init__(self, delimiter: str = ",", encoding: str = "utf-8"):
        """Initialize CSV loader.
        
        Args:
            delimiter: CSV delimiter character.
            encoding: File encoding.
        """
        self.delimiter = delimiter
        self.encoding = encoding
    
    def load(self, file_path: str) -> List[Document]:
        """Load CSV file and return as documents.
        
        Args:
            file_path: Path to CSV file.
            
        Returns:
            List of Document objects, one per row or per group.
            
        Raises:
            FileNotFoundError: If file doesn't exist.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"CSV file not found: {file_path}")
        
        documents = []
        
        try:
            import pandas as pd
            
            # Read CSV
            df = pd.read_csv(
                file_path,
                delimiter=self.delimiter,
                encoding=self.encoding
            )
            
            schema = self._infer_schema(df)
            
            # Create document with full data
            content = self._dataframe_to_text(df)
            metadata = {
                "file_name": os.path.basename(file_path),
                "total_rows": len(df),
                "total_columns": len(df.columns),
                "columns": list(df.columns),
                "schema": schema,
            }
            
            document = Document(
                content=content,
                metadata=metadata,
                source=file_path,
                doc_id=f"csv_{os.path.basename(file_path)}",
            )
            documents.append(document)
        
        except ImportError:
            # Fallback to basic text parsing
            documents = self._fallback_load(file_path)
        except Exception as e:
            raise ValueError(f"Error parsing CSV: {str(e)}")
        
        return documents
    
    def _infer_schema(self, df) -> Dict[str, str]:
        """Infer column types from dataframe.
        
        Args:
            df: Pandas dataframe.
            
        Returns:
            Dictionary of column names and types.
        """
        return {col: str(dtype) for col, dtype in df.dtypes.items()}
    
    @staticmethod
    def _dataframe_to_text(df) -> str:
        """Convert dataframe to formatted text.
        
        Args:
            df: Pandas dataframe.
            
        Returns:
            Formatted text representation.
        """
        return df.to_string()
    
    def _fallback_load(self, file_path: str) -> List[Document]:
        """Fallback loader when pandas not available.
        
        Args:
            file_path: Path to CSV file.
            
        Returns:
            List with single document.
        """
        with open(file_path, 'r', encoding=self.encoding) as f:
            content = f.read()
        
        lines = content.split('\n')
        headers = lines[0].split(self.delimiter) if lines else []
        
        document = Document(
            content=content,
            metadata={
                "file_name": os.path.basename(file_path),
                "note": "pandas not installed - basic parsing only",
                "columns": headers,
            },
            source=file_path,
        )
        return [document]


class JSONLoader:
    """Load and parse JSON files."""
    
    def __init__(self, encoding: str = "utf-8"):
        """Initialize JSON loader.
        
        Args:
            encoding: File encoding.
        """
        self.encoding = encoding
    
    def load(self, file_path: str) -> List[Document]:
        """Load JSON file and return as documents.
        
        Args:
            file_path: Path to JSON file.
            
        Returns:
            List of Document objects.
            
        Raises:
            FileNotFoundError: If file doesn't exist.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"JSON file not found: {file_path}")
        
        try:
            with open(file_path, 'r', encoding=self.encoding) as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON file: {str(e)}")
        except Exception as e:
            raise ValueError(f"Error reading JSON: {str(e)}")
        
        documents = []
        
        # Handle different JSON structures
        if isinstance(data, list):
            # Array of objects
            for idx, item in enumerate(data):
                doc = self._create_document_from_item(item, file_path, idx)
                documents.append(doc)
        elif isinstance(data, dict):
            # Single object
            doc = self._create_document_from_item(data, file_path, 0)
            documents.append(doc)
        else:
            # Scalar value
            document = Document(
                content=json.dumps(data, indent=2),
                metadata={
                    "file_name": os.path.basename(file_path),
                    "data_type": type(data).__name__,
                },
                source=file_path,
            )
            documents.append(document)
        
        return documents
    
    def _create_document_from_item(
        self,
        item: Any,
        file_path: str,
        index: int
    ) -> Document:
        """Create document from JSON item.
        
        Args:
            item: JSON item (dict, list, or scalar).
            file_path: Source file path.
            index: Item index.
            
        Returns:
            Document object.
        """
        if isinstance(item, dict):
            # Flatten nested structure
            content = self._flatten_dict_to_text(item)
            metadata = item.copy()
        else:
            content = json.dumps(item, indent=2)
            metadata = {"data_type": type(item).__name__}
        
        metadata.update({
            "file_name": os.path.basename(file_path),
            "item_index": index,
        })
        
        document = Document(
            content=content,
            metadata=metadata,
            source=file_path,
            doc_id=f"json_{os.path.basename(file_path)}_{index}",
        )
        return document
    
    @staticmethod
    def _flatten_dict_to_text(data: Dict[str, Any], prefix: str = "") -> str:
        """Convert dictionary to formatted text.
        
        Args:
            data: Dictionary to flatten.
            prefix: Key prefix for nesting.
            
        Returns:
            Formatted text representation.
        """
        lines = []
        for key, value in data.items():
            if isinstance(value, dict):
                lines.append(f"{key}:")
                lines.append(JSONLoader._flatten_dict_to_text(value, f"  {prefix}"))
            elif isinstance(value, list):
                lines.append(f"{key}: [{len(value)} items]")
            else:
                lines.append(f"{key}: {value}")
        return "\n".join(lines)
