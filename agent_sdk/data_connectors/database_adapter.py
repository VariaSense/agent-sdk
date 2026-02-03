"""Database adapter for various database systems."""

from typing import List, Dict, Any, Optional
from agent_sdk.data_connectors.document import Document
from abc import ABC, abstractmethod


class DatabaseAdapter(ABC):
    """Base class for database adapters."""
    
    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to database.
        
        Returns:
            True if connection successful.
        """
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Close database connection."""
        pass
    
    @abstractmethod
    def query(self, sql: str, params: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
        """Execute query and return results.
        
        Args:
            sql: SQL query string.
            params: Query parameters.
            
        Returns:
            List of result dictionaries.
        """
        pass
    
    @abstractmethod
    def load_table(self, table_name: str) -> List[Document]:
        """Load entire table as documents.
        
        Args:
            table_name: Name of table to load.
            
        Returns:
            List of Document objects.
        """
        pass
    
    @classmethod
    def create_for_postgres(
        cls,
        connection_string: str,
        **kwargs
    ) -> "DatabaseAdapter":
        """Factory method for PostgreSQL.
        
        Args:
            connection_string: PostgreSQL connection string.
            **kwargs: Additional arguments.
            
        Returns:
            PostgreSQL adapter instance.
        """
        return PostgresAdapter(connection_string, **kwargs)
    
    @classmethod
    def create_for_mysql(
        cls,
        connection_string: str,
        **kwargs
    ) -> "DatabaseAdapter":
        """Factory method for MySQL.
        
        Args:
            connection_string: MySQL connection string.
            **kwargs: Additional arguments.
            
        Returns:
            MySQL adapter instance.
        """
        return MySQLAdapter(connection_string, **kwargs)
    
    @classmethod
    def create_for_mongodb(
        cls,
        connection_string: str,
        **kwargs
    ) -> "DatabaseAdapter":
        """Factory method for MongoDB.
        
        Args:
            connection_string: MongoDB connection string.
            **kwargs: Additional arguments.
            
        Returns:
            MongoDB adapter instance.
        """
        return MongoDBAdapter(connection_string, **kwargs)
    
    @classmethod
    def create_for_sqlite(
        cls,
        db_path: str,
        **kwargs
    ) -> "DatabaseAdapter":
        """Factory method for SQLite.
        
        Args:
            db_path: Path to SQLite database file.
            **kwargs: Additional arguments.
            
        Returns:
            SQLite adapter instance.
        """
        return SQLiteAdapter(db_path, **kwargs)


class PostgresAdapter(DatabaseAdapter):
    """PostgreSQL database adapter."""
    
    def __init__(self, connection_string: str, **kwargs):
        """Initialize PostgreSQL adapter.
        
        Args:
            connection_string: PostgreSQL connection string.
        """
        self.connection_string = connection_string
        self.connection = None
        self._check_psycopg2()
    
    @staticmethod
    def _check_psycopg2() -> bool:
        """Check if psycopg2 is available."""
        try:
            import psycopg2
            return True
        except ImportError:
            return False
    
    def connect(self) -> bool:
        """Connect to PostgreSQL database."""
        try:
            import psycopg2
            self.connection = psycopg2.connect(self.connection_string)
            return True
        except Exception as e:
            print(f"PostgreSQL connection failed: {str(e)}")
            return False
    
    def disconnect(self) -> None:
        """Disconnect from database."""
        if self.connection:
            self.connection.close()
            self.connection = None
    
    def query(self, sql: str, params: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
        """Execute PostgreSQL query.
        
        Args:
            sql: SQL query.
            params: Query parameters.
            
        Returns:
            List of result dictionaries.
        """
        if not self.connection:
            return []
        
        try:
            cursor = self.connection.cursor()
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            
            # Get column names
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            
            # Fetch results as dicts
            results = []
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))
            
            cursor.close()
            return results
        except Exception as e:
            print(f"Query failed: {str(e)}")
            return []
    
    def load_table(self, table_name: str) -> List[Document]:
        """Load PostgreSQL table as documents.
        
        Args:
            table_name: Table name.
            
        Returns:
            List of documents.
        """
        if not self.connect():
            return []
        
        try:
            results = self.query(f"SELECT * FROM {table_name}")
            
            documents = []
            for idx, row in enumerate(results):
                content = "\n".join(f"{k}: {v}" for k, v in row.items())
                document = Document(
                    content=content,
                    metadata=row,
                    source=f"postgres://{table_name}",
                    doc_id=f"pg_{table_name}_{idx}",
                )
                documents.append(document)
            
            return documents
        finally:
            self.disconnect()


class MySQLAdapter(DatabaseAdapter):
    """MySQL database adapter."""
    
    def __init__(self, connection_string: str, **kwargs):
        """Initialize MySQL adapter.
        
        Args:
            connection_string: MySQL connection string.
        """
        self.connection_string = connection_string
        self.connection = None
    
    def connect(self) -> bool:
        """Connect to MySQL database."""
        try:
            import mysql.connector
            self.connection = mysql.connector.connect(
                connection_string=self.connection_string
            )
            return True
        except Exception as e:
            print(f"MySQL connection failed: {str(e)}")
            return False
    
    def disconnect(self) -> None:
        """Disconnect from database."""
        if self.connection:
            self.connection.close()
            self.connection = None
    
    def query(self, sql: str, params: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
        """Execute MySQL query."""
        if not self.connection:
            return []
        
        try:
            cursor = self.connection.cursor(dictionary=True)
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            
            results = cursor.fetchall()
            cursor.close()
            return results
        except Exception as e:
            print(f"Query failed: {str(e)}")
            return []
    
    def load_table(self, table_name: str) -> List[Document]:
        """Load MySQL table as documents."""
        if not self.connect():
            return []
        
        try:
            results = self.query(f"SELECT * FROM {table_name}")
            
            documents = []
            for idx, row in enumerate(results):
                content = "\n".join(f"{k}: {v}" for k, v in row.items())
                document = Document(
                    content=content,
                    metadata=row,
                    source=f"mysql://{table_name}",
                    doc_id=f"mysql_{table_name}_{idx}",
                )
                documents.append(document)
            
            return documents
        finally:
            self.disconnect()


class MongoDBAdapter(DatabaseAdapter):
    """MongoDB database adapter."""
    
    def __init__(self, connection_string: str, **kwargs):
        """Initialize MongoDB adapter.
        
        Args:
            connection_string: MongoDB connection string.
        """
        self.connection_string = connection_string
        self.client = None
        self.db = None
    
    def connect(self) -> bool:
        """Connect to MongoDB."""
        try:
            from pymongo import MongoClient
            self.client = MongoClient(self.connection_string)
            # Test connection
            self.client.admin.command('ismaster')
            return True
        except Exception as e:
            print(f"MongoDB connection failed: {str(e)}")
            return False
    
    def disconnect(self) -> None:
        """Disconnect from database."""
        if self.client:
            self.client.close()
            self.client = None
    
    def query(self, sql: str, params: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
        """Execute MongoDB query (as aggregation pipeline)."""
        # Note: 'sql' parameter expected to be collection.field syntax
        # This is simplified for basic usage
        return []
    
    def load_table(self, table_name: str) -> List[Document]:
        """Load MongoDB collection as documents."""
        if not self.connect():
            return []
        
        try:
            # Parse database and collection from table_name (db.collection format)
            parts = table_name.split('.')
            db_name = parts[0] if len(parts) > 1 else 'test'
            collection_name = parts[1] if len(parts) > 1 else parts[0]
            
            db = self.client[db_name]
            collection = db[collection_name]
            
            documents = []
            for idx, doc in enumerate(collection.find().limit(100)):
                # Convert ObjectId to string
                if '_id' in doc:
                    doc['_id'] = str(doc['_id'])
                
                content = "\n".join(f"{k}: {v}" for k, v in doc.items())
                document = Document(
                    content=content,
                    metadata=doc,
                    source=f"mongodb://{collection_name}",
                    doc_id=f"mongo_{collection_name}_{idx}",
                )
                documents.append(document)
            
            return documents
        finally:
            self.disconnect()


class SQLiteAdapter(DatabaseAdapter):
    """SQLite database adapter."""
    
    def __init__(self, db_path: str, **kwargs):
        """Initialize SQLite adapter.
        
        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = db_path
        self.connection = None
    
    def connect(self) -> bool:
        """Connect to SQLite database."""
        try:
            import sqlite3
            self.connection = sqlite3.connect(self.db_path)
            self.connection.row_factory = sqlite3.Row
            return True
        except Exception as e:
            print(f"SQLite connection failed: {str(e)}")
            return False
    
    def disconnect(self) -> None:
        """Disconnect from database."""
        if self.connection:
            self.connection.close()
            self.connection = None
    
    def query(self, sql: str, params: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
        """Execute SQLite query."""
        if not self.connection:
            return []
        
        try:
            cursor = self.connection.cursor()
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            
            results = [dict(row) for row in cursor.fetchall()]
            cursor.close()
            return results
        except Exception as e:
            print(f"Query failed: {str(e)}")
            return []
    
    def load_table(self, table_name: str) -> List[Document]:
        """Load SQLite table as documents."""
        if not self.connect():
            return []
        
        try:
            results = self.query(f"SELECT * FROM {table_name}")
            
            documents = []
            for idx, row in enumerate(results):
                content = "\n".join(f"{k}: {v}" for k, v in row.items())
                document = Document(
                    content=content,
                    metadata=row,
                    source=f"sqlite://{table_name}",
                    doc_id=f"sqlite_{table_name}_{idx}",
                )
                documents.append(document)
            
            return documents
        finally:
            self.disconnect()
