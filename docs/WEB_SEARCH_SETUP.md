# Web Search Setup Guide

This guide explains how to enable and configure web searching functionality in the AI Model Card Generator.

## Overview

The web search functionality allows the system to discover official websites, documentation, and relevant sources for dermatology AI models by searching the web using various search engines and APIs.

## Features

- **Single Search Provider**: DuckDuckGo (no API key required)
- **Automatic Fallback**: If API-based providers fail, the system falls back to DuckDuckGo
- **Rate Limiting**: Built-in delays between searches to be respectful to APIs
- **Configuration Options**: Environment variables for easy configuration
- **Error Handling**: Robust error handling with graceful degradation

## Quick Start

### 1. Basic Setup (No API Keys Required)

Web search is enabled by default and will work with DuckDuckGo as a fallback provider:

```bash
# Web search is enabled by default
# No additional setup required for basic functionality
```

### 2. Test Web Search

Run the test script to verify web search is working:

```bash
python test_web_search.py
```

## Configuration

### Environment Variables

Configure web search using the following environment variables:

#### Basic Configuration

```bash
# Enable/disable web search (default: true)
export WEB_SEARCH_ENABLED=true

# Preferred search provider (default: auto)
# Options: auto, google, bing, duckduckgo, serpapi
export WEB_SEARCH_PROVIDER=auto

# Maximum results per search (default: 10)
export WEB_SEARCH_MAX_RESULTS=10

# Delay between searches in seconds (default: 0.5)
export WEB_SEARCH_DELAY_SECONDS=0.5
```

#### API Provider Configuration

**Google Custom Search API**
```bash
export GOOGLE_SEARCH_API_KEY=your_google_api_key
export GOOGLE_SEARCH_ENGINE_ID=your_search_engine_id
```

**Bing Search API**
```bash
export BING_SEARCH_API_KEY=your_bing_api_key
```

**SerpAPI**
```bash
export SERPAPI_KEY=your_serpapi_key
```

### Setting Up API Providers

#### Google Custom Search API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable the Custom Search API
4. Create credentials (API Key)
5. Create a Custom Search Engine at [Google Custom Search](https://cse.google.com/)
6. Get your Search Engine ID
7. Set the environment variables:
   ```bash
   export GOOGLE_SEARCH_API_KEY=your_api_key
   export GOOGLE_SEARCH_ENGINE_ID=your_search_engine_id
   ```

#### Bing Search API

1. Go to [Azure Portal](https://portal.azure.com/)
2. Create a Bing Search resource
3. Get your API key
4. Set the environment variable:
   ```bash
   export BING_SEARCH_API_KEY=your_api_key
   ```

#### SerpAPI

1. Sign up at [SerpAPI](https://serpapi.com/)
2. Get your API key from the dashboard
3. Set the environment variable:
   ```bash
   export SERPAPI_KEY=your_api_key
   ```

## Usage in the Pipeline

Web search is automatically integrated into the model card generation pipeline. It's used in several places:

### 1. General Web Sources Search

Searches for official websites and documentation:
- `"{model_name}" official website`
- `"{model_name}" documentation`
- `"{model_name}" medical device`
- `"{model_name}" FDA approval`

### 2. Developer-Specific Search

When a developer name is provided, searches for:
- `site:{developer_domain} "{model_name}"`
- `"{developer_name}" "{model_name}" official`
- `"{developer_name}" "{model_name}" documentation`

### 3. General Web Discovery

Enhanced search for comprehensive source discovery:
- Official websites
- Company sites
- Documentation pages
- Regulatory information

## Search Results Format

Web search results include:

```python
{
    'url': 'https://example.com/page',
    'title': 'Page Title',
    'snippet': 'Page description...',
    'source': 'google_custom_search',  # or 'bing_search', 'duckduckgo', 'serpapi'
    'rank': 1,
    'source_type': 'web_search',
    'discovery_method': 'web_search',
    'relevance_score': 0.8,
    'query_used': 'search query that found this result'
}
```

## Troubleshooting

### Common Issues

**Web search not working:**
- Check that `WEB_SEARCH_ENABLED=true`
- Verify network connectivity
- Check API key validity (if using API providers)

**No results found:**
- Try different search queries
- Check if the model/developer names are correct
- Verify API quotas haven't been exceeded

**Rate limiting errors:**
- Increase `WEB_SEARCH_DELAY_SECONDS`
- Check API provider quotas
- Consider using multiple providers

### Debug Mode

Enable debug logging to see detailed web search activity:

```bash
export PYTHONPATH=src
python -c "
import logging
logging.basicConfig(level=logging.DEBUG)
from utils.web_search import web_search
import asyncio
asyncio.run(web_search('test query', max_results=3))
"
```

## Performance Considerations

- **API Costs**: API-based providers may have usage costs
- **Rate Limits**: Built-in delays prevent hitting rate limits
- **Fallback**: DuckDuckGo provides free fallback functionality
- **Caching**: Results are not cached by default (can be added if needed)

## Security Notes

- API keys are read from environment variables only
- No API keys are stored in code or configuration files
- HTTPS is enforced for all API communications
- User agents identify the application for transparency

## Integration Examples

### Using Web Search in Custom Code

```python
from utils.web_search import web_search, is_web_search_available

async def my_search_function():
    if not is_web_search_available():
        print("Web search not available")
        return []
    
    results = await web_search("dermatology AI model", max_results=5)
    return results
```

### Checking Available Providers

```python
from utils.web_search import get_web_search_providers

providers = get_web_search_providers()
print(f"Available providers: {providers}")
```

## Support

For issues with web search functionality:

1. Run the test script: `python test_web_search.py`
2. Check the configuration section above
3. Verify API keys and quotas
4. Check network connectivity
5. Review the logs for error messages

The web search functionality is designed to be robust and will gracefully degrade if providers are unavailable, ensuring the model card generation process continues even if web search fails.
