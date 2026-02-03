"""Web content scraper."""

from typing import List, Optional, Set
from agent_sdk.data_connectors.document import Document
import os


class WebScraper:
    """Extract content from websites."""
    
    def __init__(self, timeout: int = 10, headers: Optional[dict] = None):
        """Initialize web scraper.
        
        Args:
            timeout: Request timeout in seconds.
            headers: Custom HTTP headers.
        """
        self.timeout = timeout
        self.headers = headers or {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        self._requests_available = self._check_requests()
        self._beautifulsoup_available = self._check_beautifulsoup()
    
    @staticmethod
    def _check_requests() -> bool:
        """Check if requests library is available."""
        try:
            import requests
            return True
        except ImportError:
            return False
    
    @staticmethod
    def _check_beautifulsoup() -> bool:
        """Check if beautifulsoup4 is available."""
        try:
            from bs4 import BeautifulSoup
            return True
        except ImportError:
            return False
    
    def scrape_url(self, url: str) -> Document:
        """Fetch and parse webpage content.
        
        Args:
            url: URL to scrape.
            
        Returns:
            Document with webpage content.
            
        Raises:
            ValueError: If URL is invalid or fetch fails.
        """
        if not url.startswith(('http://', 'https://')):
            raise ValueError(f"Invalid URL: {url}")
        
        try:
            import requests
            from bs4 import BeautifulSoup
        except ImportError:
            return self._fallback_scrape(url)
        
        try:
            response = requests.get(
                url,
                timeout=self.timeout,
                headers=self.headers
            )
            response.raise_for_status()
        except Exception as e:
            raise ValueError(f"Failed to fetch URL: {str(e)}")
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract text
        text = self._extract_text(soup)
        
        # Extract metadata
        metadata = self._extract_metadata(soup, url, response)
        
        document = Document(
            content=text,
            metadata=metadata,
            source=url,
            doc_id=f"web_{hash(url) & 0x7fffffff}",
        )
        
        return document
    
    def extract_links(self, url: str) -> List[str]:
        """Find all links on a page.
        
        Args:
            url: URL to scrape.
            
        Returns:
            List of absolute URLs found on page.
        """
        if not url.startswith(('http://', 'https://')):
            raise ValueError(f"Invalid URL: {url}")
        
        try:
            import requests
            from bs4 import BeautifulSoup
            from urllib.parse import urljoin
        except ImportError:
            return []
        
        try:
            response = requests.get(
                url,
                timeout=self.timeout,
                headers=self.headers
            )
            response.raise_for_status()
        except Exception:
            return []
        
        soup = BeautifulSoup(response.content, 'html.parser')
        links = []
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            # Convert relative URLs to absolute
            absolute_url = urljoin(url, href)
            if absolute_url.startswith(('http://', 'https://')):
                links.append(absolute_url)
        
        return list(set(links))
    
    @staticmethod
    def _extract_text(soup) -> str:
        """Extract clean text from BeautifulSoup object.
        
        Args:
            soup: BeautifulSoup parsed HTML.
            
        Returns:
            Clean text content.
        """
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Get text
        text = soup.get_text()
        
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        return text
    
    @staticmethod
    def _extract_metadata(soup, url: str, response) -> dict:
        """Extract metadata from webpage.
        
        Args:
            soup: BeautifulSoup parsed HTML.
            url: Page URL.
            response: Requests response object.
            
        Returns:
            Metadata dictionary.
        """
        metadata = {
            "url": url,
            "status_code": response.status_code,
            "encoding": response.encoding,
        }
        
        # Extract title
        title_tag = soup.find('title')
        if title_tag:
            metadata["title"] = title_tag.get_text()
        
        # Extract meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            metadata["description"] = meta_desc.get('content', '')
        
        # Extract all meta tags
        meta_tags = {}
        for meta in soup.find_all('meta'):
            name = meta.get('name', meta.get('property', ''))
            if name:
                meta_tags[name] = meta.get('content', '')
        metadata["meta_tags"] = meta_tags
        
        return metadata
    
    @staticmethod
    def _fallback_scrape(url: str) -> Document:
        """Fallback when libraries not available.
        
        Args:
            url: URL to scrape.
            
        Returns:
            Document with URL info.
        """
        document = Document(
            content=f"[Webpage: {url}] - Install requests and beautifulsoup4 for content extraction",
            metadata={
                "url": url,
                "note": "requests or beautifulsoup4 not installed",
            },
            source=url,
        )
        return document
