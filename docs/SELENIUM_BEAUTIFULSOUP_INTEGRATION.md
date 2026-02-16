# Beautiful Soup & Selenium Integration Guide

This document explains how Beautiful Soup and Selenium work together to improve model card content extraction.

## Overview

The model card generator now uses a **hybrid scraping approach**:

1. **Beautiful Soup** (fast, static) - Primary method for most websites
2. **Selenium** (slower, dynamic) - Fallback for JavaScript-rendered content

This combination ensures we can extract content from both traditional HTML pages and modern single-page applications (SPAs) built with React, Vue, Angular, etc.

## Architecture

### Components

1. **`src/scrapers/selenium_scraper.py`** - New Selenium-based scraper
   - Handles JavaScript-rendered pages
   - Uses Beautiful Soup for parsing rendered HTML
   - Supports Chrome and Firefox (headless mode)

2. **`src/scrapers/robust_scraper_v2.py`** - Enhanced with Selenium fallback
   - Tries static scraping first (fast)
   - Automatically falls back to Selenium when needed
   - Detects JavaScript indicators

3. **`src/utils/web_search.py`** - Updated to use Selenium fallback
   - Checks content length after static extraction
   - Uses Selenium if content seems incomplete

## How It Works

### Detection Logic

The system detects JavaScript-rendered content by checking for:

1. **Content length** - If extracted text is < 200 characters, likely needs JS
2. **JavaScript indicators**:
   - `<noscript>` tags
   - "Enable JavaScript" messages
   - React/Angular/Vue markers (`react-root`, `ng-app`, etc.)
   - Next.js data (`__NEXT_DATA__`)
   - Empty or minimal body content

### Workflow

```
1. Try static scraping (Beautiful Soup + aiohttp)
   ↓
2. Check if content is sufficient
   ↓
3. If content < 200 chars OR has JS indicators:
   → Try Selenium fallback
   ↓
4. Compare results, use best content
   ↓
5. Cache result for future use
```

## Usage Examples

### Basic Usage (Automatic)

The system automatically uses Selenium when needed:

```python
from scrapers.robust_scraper_v2 import RobustWebScraper

async with RobustWebScraper() as scraper:
    # Automatically tries Selenium if needed
    result = await scraper.extract_content_from_url("https://example.com/spa")
    
    if result['status'] == 'success':
        print(f"Extracted {len(result['clean_text'])} characters")
        print(f"Selenium used: {result['diagnostics'].get('selenium_fallback_used', False)}")
```

### Direct Selenium Usage

For pages you know require JavaScript:

```python
from scrapers.selenium_scraper import scrape_with_selenium

result = await scrape_with_selenium(
    url="https://example.com/react-app",
    browser="chrome",  # or "firefox"
    headless=True,
    wait_for_content=True
)

if result['status'] == 'success':
    print(result['clean_text'])
    print(result['metadata'])
```

### Manual Detection

Check if a page needs Selenium:

```python
from scrapers.selenium_scraper import needs_selenium

html = "<html><body><noscript>Enable JavaScript</noscript></body></html>"
if needs_selenium(html):
    # Use Selenium
    pass
```

## Benefits for Model Card Generation

### 1. **Better Content Extraction**

- **Before**: Missing content from React/Vue/Angular apps
- **After**: Full content extraction from modern web apps

### 2. **Improved Metadata**

- Extracts JSON-LD structured data from rendered pages
- Captures Open Graph and Twitter Card metadata
- Better heading and link extraction

### 3. **Enhanced Model Card Quality**

- More complete model descriptions
- Better performance metrics extraction
- Improved regulatory information discovery

### 4. **Automatic Fallback**

- No manual configuration needed
- Fast for static pages, thorough for dynamic pages
- Caching prevents redundant Selenium calls

## Configuration

### Browser Selection

Default is Chrome (headless). To use Firefox:

```python
from scrapers.selenium_scraper import SeleniumScraper

with SeleniumScraper(browser="firefox", headless=True) as scraper:
    result = scraper.scrape_url("https://example.com")
```

### Timeouts

Adjust wait times for slow-loading pages:

```python
scraper = SeleniumScraper(
    wait_timeout=15,      # Wait up to 15s for content
    page_load_timeout=60,  # Allow 60s for page load
    implicit_wait=10      # Wait 10s for elements
)
```

### Disable Selenium Fallback

If you want to use only static scraping:

```python
# In robust_scraper_v2.py, the fallback is automatic
# To disable, you'd need to modify the code or use web_search directly:

from utils.web_search import fetch_many

# This won't use Selenium fallback
results = await fetch_many(urls, concurrency=6)
```

## Performance Considerations

### Speed

- **Static scraping**: ~0.5-2 seconds per page
- **Selenium scraping**: ~3-10 seconds per page

The system only uses Selenium when needed, so most pages remain fast.

### Resource Usage

- Selenium requires more memory (~100-200MB per browser instance)
- Chrome/Firefox drivers are automatically managed
- Headless mode reduces resource usage

### Caching

All results are cached, so repeated requests are fast:

```python
# First request: May use Selenium (3-10s)
result1 = await scraper.extract_content_from_url(url)

# Second request: Uses cache (<0.1s)
result2 = await scraper.extract_content_from_url(url)
```

## Troubleshooting

### Selenium Not Available

If you see `SELENIUM_AVAILABLE = False`:

```bash
pip install selenium webdriver-manager
```

### Browser Driver Issues

The `webdriver-manager` package automatically downloads drivers. If you have issues:

1. Check internet connection (for driver download)
2. Ensure Chrome/Firefox is installed
3. Try specifying driver path manually

### Timeout Errors

If pages timeout:

```python
scraper = SeleniumScraper(
    page_load_timeout=60,  # Increase timeout
    wait_timeout=20        # Wait longer for content
)
```

### Memory Issues

If running out of memory:

1. Use headless mode (default)
2. Close browsers promptly (use context manager)
3. Reduce concurrent Selenium instances

## Best Practices

1. **Use context managers** - Ensures browsers are closed properly
2. **Enable caching** - Reduces redundant Selenium calls
3. **Monitor diagnostics** - Check `diagnostics` field to see what method was used
4. **Handle errors gracefully** - Selenium can fail, static scraping is fallback
5. **Test with known JS pages** - Verify Selenium works for your use case

## Example: Complete Workflow

```python
import asyncio
from scrapers.robust_scraper_v2 import RobustWebScraper

async def extract_model_info(model_url: str):
    async with RobustWebScraper() as scraper:
        # Automatically uses Selenium if needed
        result = await scraper.extract_content_from_url(model_url)
        
        if result['status'] == 'success':
            print(f"Title: {result['title']}")
            print(f"Content: {result['clean_text'][:500]}...")
            print(f"Used Selenium: {result['diagnostics'].get('selenium_fallback_used', False)}")
            
            # Extract structured data
            json_ld = result['metadata'].get('json_ld', {})
            if json_ld:
                print(f"JSON-LD: {json_ld}")
        else:
            print(f"Error: {result.get('error', 'Unknown error')}")

# Run
asyncio.run(extract_model_info("https://example.com/model"))
```

## Integration with Model Card Pipeline

The Selenium integration is automatically used in the model card generation pipeline:

```python
from pipelines.cardgen_pipeline import CardGenPipeline

async with CardGenPipeline() as pipeline:
    # This automatically uses Selenium when needed
    card, sources, content = await pipeline.generate_model_card(
        model_name="DermGPT",
        developer_name="Example Corp",
        application_url="https://example.com/dermgpt"  # May be a React app
    )
```

The pipeline's `discover_model_sources` and content extraction methods automatically benefit from Selenium fallback.

## Summary

The Beautiful Soup + Selenium integration provides:

✅ **Fast static scraping** for traditional websites  
✅ **Thorough dynamic scraping** for JavaScript apps  
✅ **Automatic detection** and fallback  
✅ **Better content extraction** for model cards  
✅ **Caching** for performance  
✅ **Zero configuration** needed  

This ensures the model card generator can extract high-quality content from any type of website, improving the completeness and accuracy of generated model cards.

