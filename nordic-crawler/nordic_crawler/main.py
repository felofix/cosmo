from pathlib import Path
import json
import asyncio
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, unquote
from typing import Set, List, Dict, Optional
from crawl4ai import AsyncWebCrawler
import re
import datetime
import argparse
from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException

class UDICrawler:
    def __init__(self, 
                 start_urls: List[str], 
                 allowed_domains: List[str],
                 max_depth: int = 3, 
                 output_dir: Path = Path('output'),
                 output_format: str = 'json',
                 output_filename: str = None):
        self.start_urls = start_urls
        self.allowed_domains = allowed_domains
        self.max_depth = max_depth
        self.output_dir = output_dir
        self.output_dir.mkdir(exist_ok=True)
        self.output_format = output_format.lower()
        if self.output_format not in ['json', 'markdown']:
            raise ValueError("output_format must be either 'json' or 'markdown'")
        
        # Set default output filename if none provided
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_filename = output_filename or f"nordic_pages_{timestamp}"
        
        # URL tracking
        self.visited_urls: Set[str] = set()
        self.found_urls: Set[str] = set()
        self.processed_pages: List[Dict] = []
        
        # Progress tracking
        self.total_processed = 0
        self.rag_documents: List[Dict] = []
        
        # Save intermediate state periodically
        self.save_interval = 5  # Save every 5 pages
    
    def normalize_url(self, url: str) -> str:
        """Normalize URL to prevent duplicates with different formats."""
        # Remove trailing slashes
        url = url.rstrip('/')
        # Decode URL-encoded characters
        url = unquote(url)
        # Remove common tracking parameters
        parsed = urlparse(url)
        # Remove fragments
        url = url.split('#')[0]
        return url
    
    def should_crawl_url(self, url: str) -> bool:
        """Check if a URL should be crawled based on domain and file type."""
        if not url:
            return False
            
        parsed = urlparse(url)
        # Check if domain is in allowed domains
        if not any(parsed.netloc.endswith(domain) for domain in self.allowed_domains):
            return False
            
        # Skip non-HTML files
        skip_extensions = {'.pdf', '.jpg', '.jpeg', '.png', '.gif', '.doc', '.docx'}
        if any(parsed.path.lower().endswith(ext) for ext in skip_extensions):
            return False
            
        return True
    
    def should_process_url(self, url: str) -> bool:
        """Check if a URL's content should be processed based on patterns."""
        # If no patterns are specified, process all crawled URLs
        return True
    
    def extract_links(self, html_content: str, base_url: str) -> Set[str]:
        """Extract all valid links from the HTML content."""
        soup = BeautifulSoup(html_content, 'html.parser')
        links = set()
        
        for a_tag in soup.find_all('a', href=True):
            href = a_tag.get('href', '').strip()
            if not href:
                continue
                
            # Convert relative URLs to absolute
            absolute_url = urljoin(base_url, href)
            normalized_url = self.normalize_url(absolute_url)
            
            # Only include URLs we should crawl
            if self.should_crawl_url(normalized_url):
                links.add(normalized_url)
                self.found_urls.add(normalized_url)
        
        return links
    
    def extract_content(self, element) -> str:
        """Extract content from BeautifulSoup object or string with improved whitespace handling."""
        if isinstance(element, str):
            # If it's already a string, just normalize whitespace
            return ' '.join(element.split())
            
        # If it's a BeautifulSoup object, process it
        # Remove script and style elements
        for script in element.find_all(["script", "style"]):
            script.decompose()

        # Replace <br> tags with newlines before getting text
        for br in element.find_all('br'):
            br.replace_with('\n')

        # Insert space between adjacent elements that might need it
        for elem in element.find_all(['p', 'div', 'span', 'a']):
            if elem.next_sibling and isinstance(elem.next_sibling, str):
                elem.insert_after(' ')

        # Get text while preserving some structure
        text = ''
        for element in element.descendants:
            if isinstance(element, str):
                text += element
            elif element.name in ['p', 'div', 'br']:
                text += '\n'

        # Normalize whitespace while preserving meaningful spaces
        # First split on newlines and handle each line separately
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            # Normalize spaces within each line
            cleaned_line = ' '.join(word for word in line.split() if word)
            if cleaned_line:
                cleaned_lines.append(cleaned_line)

        # Join lines with appropriate spacing
        text = '\n'.join(cleaned_lines)
        
        # Remove any excessive newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text.strip()
    
    def should_skip_element(self, element) -> bool:
        """Check if an element should be skipped."""
        if not element:
            return True
        
        # Skip elements with specific classes
        skip_classes = ['breadcrumb', 'navigation', 'menu', 'related-content', 'LinkMessageBlockView']
        if any(cls in str(element.get('class', [])) for cls in skip_classes):
            return True
            
        if element.name == 'a' and not element.find_parent(['p', 'li']):
            return True
            
        # Skip elements with specific text patterns
        skip_patterns = ['this is the file:', 'LinkMessageBlockView']
        if any(pattern in element.get_text() for pattern in skip_patterns):
            return True
            
        return False

    def clean_text(self, text: str) -> str:
        """Clean text by removing template text, duplicates and normalizing whitespace."""
        # Remove template text patterns
        text = re.sub(r'this is the file:.*?(?=\S)', '', text)
        text = re.sub(r'LinkMessageBlockView\s*', '', text)
        
        # Split into sentences/items
        items = []
        for line in text.split('\n'):
            # Split line into sentences
            sentences = [s.strip() for s in re.split(r'[.!?]', line) if s.strip()]
            items.extend(sentences)
        
        # Remove duplicates while preserving order
        seen = set()
        clean_items = []
        for item in items:
            # Skip items that are just ID strings (no spaces)
            if ' ' not in item:
                continue
            # Skip items that are just numbers
            if item.replace(' ', '').isdigit():
                continue
            # Skip items that are too short
            if len(item) < 5:
                continue
            # Skip duplicates
            normalized_item = ' '.join(item.lower().split())
            if normalized_item not in seen:
                clean_items.append(item)
                seen.add(normalized_item)
        
        # Join back with appropriate punctuation/newlines
        result = []
        for item in clean_items:
            # Check if it's a list item
            if item.startswith('-'):
                result.append(item)
            else:
                result.append(item + '.')
        
        return '\n'.join(result)

    def extract_content_from_html(self, html_content: str, url: str) -> Optional[dict]:
        """Extract content from HTML."""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find the main content area - UDI specific
        main_content = soup.find(['article', 'main']) or soup.find('div', class_='content')
        if not main_content:
            return None
        
        # Get the title
        title = soup.find(['h1', 'title'])
        title_text = title.get_text(strip=True) if title else url
        
        # Extract headings and their associated content
        sections = []
        current_heading = None
        current_content = []
        all_text = title_text + "\n"  # Start with title for language detection
        
        for element in main_content.find_all(['h2', 'h3', 'p', 'ul', 'ol', 'div']):
            if self.should_skip_element(element):
                continue
                
            if element.name in ['h2', 'h3']:
                if current_heading and current_content:
                    clean_content = []
                    seen_content = set()
                    
                    for content in current_content:
                        clean_text_content = self.extract_content(content)
                        if clean_text_content and clean_text_content not in seen_content:
                            if not any(clean_text_content.startswith(h['heading']) for h in sections):
                                clean_content.append(clean_text_content)
                                seen_content.add(clean_text_content)
                                all_text += clean_text_content + "\n"
                    
                    if clean_content:
                        combined_content = '\n'.join(clean_content)
                        cleaned_combined_content = self.clean_text(combined_content)
                        sections.append({
                            'heading': self.extract_content(current_heading),
                            'content': cleaned_combined_content
                        })
                
                current_heading = element
                current_content = []
            else:
                if element.name in ['ul', 'ol']:
                    items = []
                    for li in element.find_all('li'):
                        if not self.should_skip_element(li):
                            item_text = self.extract_content(li)
                            if item_text and not item_text.endswith('...'):
                                items.append(f"- {item_text}")
                    if items:
                        current_content.append('\n'.join(items))
                elif element.name in ['p', 'div']:
                    text = self.extract_content(element)
                    if text:
                        if not any(text.startswith(h['heading']) for h in sections):
                            current_content.append(text)
        
        # Add the last section
        if current_heading and current_content:
            clean_content = []
            seen_content = set()
            for content in current_content:
                clean_text_content = self.extract_content(content)
                if clean_text_content and clean_text_content not in seen_content:
                    if not any(clean_text_content.startswith(h['heading']) for h in sections):
                        clean_content.append(clean_text_content)
                        seen_content.add(clean_text_content)
                        all_text += clean_text_content + "\n"
            
            if clean_content:
                combined_content = '\n'.join(clean_content)
                cleaned_combined_content = self.clean_text(combined_content)
                sections.append({
                    'heading': self.extract_content(current_heading),
                    'content': cleaned_combined_content
                })
        
        if not sections:
            return None

        # Detect language from all collected text
        language = self.detect_language(all_text)
            
        return {
            'url': url,
            'title': title_text,
            'sections': sections,
            'language': language
        }
    
    def detect_language(self, content: str) -> str:
        """Detect the language of the given text content."""
        try:
            # Combine a reasonable amount of text for better language detection
            return detect(content[:10000])  # Use first 10000 chars for faster processing
        except LangDetectException:
            # If language detection fails, try to determine from URL
            if '/no/' in content:
                return 'no'
            elif '/en/' in content:
                return 'en'
            return 'unknown'

    def save_page(self, page: Dict):
        """Save a single page to files."""
        # Create markdown content
        markdown_content = f"# {page['title']}\n\n"
        for section in page['sections']:
            markdown_content += f"## {section['heading']}\n\n{section['content']}\n\n"
        
        # Create a safe filename from the title
        safe_title = re.sub(r'[^\w\s-]', '', page['title'])
        safe_title = re.sub(r'[-\s]+', '_', safe_title).strip('-_')
        safe_title = safe_title[:100]  # Limit length
        
        # Save markdown file
        with open(self.output_dir / f"{safe_title}.md", 'w', encoding='utf-8') as f:
            f.write(f"{page['url']}\n\n{markdown_content}")
        
        # Add to RAG documents
        for section in page['sections']:
            self.rag_documents.append({
                'url': page['url'],
                'title': page['title'],
                'heading': section['heading'],
                'content': section['content'],
                'metadata': {
                    'type': 'nordic_guide',
                    'source': 'nordic government websites',
                    'language': page['language']
                }
            })
        
        self.processed_pages.append(page)
        self.total_processed += 1
        
        # Save intermediate results periodically
        if self.total_processed % self.save_interval == 0:
            self.save_intermediate_results()
    
    def save_intermediate_results(self):
        """Save current results to files."""
        if not self.processed_pages:
            return

        # Save in the specified format
        if self.output_format == 'json':
            output_file = self.output_dir / f"{self.output_filename}.json"
            # Convert to RAG format
            rag_documents = []
            for page in self.processed_pages:
                for section in page['sections']:
                    rag_documents.append({
                        'url': page['url'],
                        'title': page['title'],
                        'heading': section['heading'],
                        'content': section['content'],
                        'metadata': {
                            'type': 'nordic_guide',
                            'source': 'nordic government websites',
                            'language': page.get('language', 'unknown')
                        }
                    })
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(rag_documents, f, ensure_ascii=False, indent=2)
        else:  # markdown
            output_file = self.output_dir / f"{self.output_filename}.md"
            with open(output_file, 'w', encoding='utf-8') as f:
                for page in self.processed_pages:
                    f.write(f"# {page['title']}\n\n")
                    f.write(f"URL: {page['url']}\n\n")
                    f.write(f"Language: {page.get('language', 'unknown')}\n\n")
                    for section in page.get('sections', []):
                        f.write(f"## {section['heading']}\n\n")
                        f.write(f"{section['content']}\n\n")
                    f.write("---\n\n")
    
    async def crawl_url(self, url: str, depth: int, crawler: AsyncWebCrawler) -> None:
        """Crawl a single URL and extract its content."""
        try:
            if url in self.visited_urls:
                return
            
            self.visited_urls.add(url)
            print(f"\nCrawling {url} (depth {depth})")
            print(f"Progress: {self.total_processed} pages processed out of {len(self.found_urls)} found URLs")
            
            # Get page content
            result = await crawler.arun(url=url)
            if not result or not result.html:
                print(f"Failed to fetch content from {url}")
                return
            
            # Extract and follow links if not at max depth
            if depth < self.max_depth:
                links = self.extract_links(result.html, url)
                for link in links:
                    await self.crawl_url(link, depth + 1, crawler)
            
            # Only process content if URL matches patterns
            if self.should_process_url(url):
                content = self.extract_content_from_html(result.html, url)
                if content:
                    self.processed_pages.append(content)
                    self.total_processed += 1
                    print(f"Successfully processed page {self.total_processed} of {len(self.found_urls)}")
                    
                    # Save intermediate results periodically
                    if self.total_processed % self.save_interval == 0:
                        self.save_intermediate_results()
                    
        except Exception as e:
            import traceback
            print(f"Error crawling {url}:")
            traceback.print_exc()
    
    async def crawl(self) -> List[Dict]:
        """Start the crawling process from all initial URLs."""
        async with AsyncWebCrawler() as crawler:
            # Start crawling from each start URL
            for start_url in self.start_urls:
                await self.crawl_url(start_url, 0, crawler)
            
            return self.processed_pages

async def async_main():
    """Entry point for the crawler."""
    parser = argparse.ArgumentParser(description='Crawl Nordic government websites')
    parser.add_argument('--max-depth', type=int, default=3,
                      help='Maximum depth to crawl')
    parser.add_argument('--output-dir', type=Path, default=Path('output'),
                      help='Output directory for crawled content')
    parser.add_argument('--output-format', choices=['json', 'markdown'], 
                      default='json', help='Output format')
    parser.add_argument('--output-filename', 
                      help='Base name for output file (without extension)')
    parser.add_argument('--domains', nargs='+', default=['udi.no'],
                      help='List of domains to crawl (e.g., udi.no skatteetaten.no)')
    
    args = parser.parse_args()
    
    # Map domains to their start URLs
    domain_urls = {
        'udi.no': ['https://udi.no/en', 'https://udi.no/no'],
        'skatteetaten.no': ['https://www.skatteetaten.no/en/', 'https://www.skatteetaten.no/no/']
    }
    
    # Collect start URLs for selected domains
    start_urls = []
    for domain in args.domains:
        if domain in domain_urls:
            start_urls.extend(domain_urls[domain])
        else:
            print(f"Warning: No predefined URLs for domain {domain}")
            # Add a default URL pattern
            start_urls.extend([f'https://www.{domain}', f'https://{domain}'])
    
    crawler = UDICrawler(
        start_urls=start_urls,
        allowed_domains=args.domains,
        max_depth=args.max_depth,
        output_dir=args.output_dir,
        output_format=args.output_format,
        output_filename=args.output_filename
    )
    
    await crawler.crawl()

def main():
    """Entry point for the crawler."""
    asyncio.run(async_main())

if __name__ == "__main__":
    main()
