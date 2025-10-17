# Caching System for Model Card Generation

## Overview

This comprehensive caching system has been implemented to track and store all scraped and extracted information during model card generation. This enables debugging of incomplete model cards by allowing inspection of what data was actually retrieved and processed at each stage.

## Features

- **Multi-level caching**: Captures data at web scraping, AI extraction, and pipeline stages
- **Detailed logging**: Tracks cache hits/misses with comprehensive metadata
- **Data inspection tools**: Debug why model cards aren't being fully filled out
- **Automatic cache management**: Cleanup, compression, and size limits
- **Export capabilities**: Export cached data for analysis
- **Performance monitoring**: Cache statistics and hit rates

## Components

### 1. Core Cache System (`src/utils/cache_system.py`)

The main caching infrastructure with:
- SQLite database for persistent storage
- Memory cache for fast access
- Compression and serialization
- Automatic cleanup and size management
- Multi-source data organization

### 2. Integrated Caching

Caching has been integrated into key components:

#### Web Search (`src/utils/web_search.py`)
- Caches DuckDuckGo search results
- Caches web page fetches (HTML/PDF)
- Caches model source discovery

#### Gemini Agent (`src/agents/gemini_agent/agent.py`)
- Caches planning results
- Caches field extraction results
- Caches validation results

#### Robust Scraper (`src/scrapers/robust_scraper_v2.py`)
- Caches scraped content
- Caches PDF extraction results
- Caches error results for debugging

### 3. Debug Tools

#### Cache Inspector (`cache_inspector.py`)
Comprehensive inspection tool with commands:

```bash
# Show cache statistics
python cache_inspector.py --stats --cache-dir cache

# Inspect cached data for a model
python cache_inspector.py --model "Derm Foundation" --developer "Google Health" --cache-dir cache

# Debug missing fields
python cache_inspector.py --debug "Derm Foundation" --developer "Google Health" --cache-dir cache

# Export cache data
python cache_inspector.py --export "Derm Foundation" --output derm_cache.json --cache-dir cache

# Clear cache for a model
python cache_inspector.py --clear "Derm Foundation" --cache-dir cache
```

#### Test Script (`test_caching.py`)
Comprehensive test suite that verifies:
- Web search caching
- Model source discovery caching
- Robust scraper caching
- Gemini agent caching
- Cache inspection capabilities
- Cache export functionality

## Usage Examples

### Running with Derm Foundation Model

```bash
# Test the caching system
python test_caching.py

# Inspect cached data
python cache_inspector.py --model "Derm Foundation" --developer "Google Health" --cache-dir test_cache

# Debug missing information
python cache_inspector.py --debug "Derm Foundation" --developer "Google Health" --cache-dir test_cache
```

### Cache Data Structure

The cache stores data organized by source:

- **web_search**: DuckDuckGo search results
- **web_fetch**: Fetched web page content
- **model_sources**: Discovered model sources
- **gemini_planning**: AI planning results
- **gemini_extraction**: Field extraction results
- **robust_scraper**: Scraped content with metadata

Each entry includes:
- URL and content
- Timestamp and metadata
- Model name and stage
- Performance metrics

## Debugging Model Card Issues

### Common Issues and Solutions

1. **Missing Web Search Results**
   - Check if search queries are finding relevant sources
   - Verify DuckDuckGo API is accessible
   - Review query formulation

2. **Failed Web Fetches**
   - Check URL accessibility
   - Review robots.txt compliance
   - Verify content type handling

3. **Incomplete AI Extractions**
   - Review source content quality
   - Check field extraction prompts
   - Verify Gemini API responses

4. **Missing Model Sources**
   - Improve search query diversity
   - Add more seed URLs
   - Check developer-specific domains

### Debug Workflow

1. **Run model card generation** to populate cache
2. **Inspect cache data** to see what was retrieved
3. **Export cache data** for detailed analysis
4. **Debug missing fields** to identify gaps
5. **Review recommendations** for improvements

## Performance Benefits

- **Reduced API calls**: Cached search results and extractions
- **Faster debugging**: Instant access to previous runs
- **Better reliability**: Retry failed operations with cached data
- **Cost savings**: Avoid redundant API usage

## Configuration

### Cache Settings

```python
# Default cache configuration
cache_dir = "cache"           # Cache directory
max_size_mb = 500            # Maximum cache size
cleanup_age_hours = 24       # Cache entry age limit
```

### Logging

The system provides detailed logging:
- Cache hits/misses
- Data storage/retrieval
- Performance metrics
- Error tracking

## File Structure

```
cache/                          # Cache directory
├── cache.db                   # SQLite database
├── cache_export_*.json       # Exported cache data
└── cache_stats.json          # Cache statistics

src/utils/
├── cache_system.py           # Core caching system
└── web_search.py            # Web search with caching

src/agents/gemini_agent/
└── agent.py                  # Gemini agent with caching

src/scrapers/
└── robust_scraper_v2.py     # Scraper with caching

cache_inspector.py            # Debug inspection tool
test_caching.py              # Test suite
```

## Testing

The caching system has been tested with the Derm Foundation model from Google Health, demonstrating:

- ✅ Web search result caching
- ✅ Model source discovery caching  
- ✅ Web content fetching caching
- ✅ Gemini agent planning caching
- ✅ Field extraction caching
- ✅ Cache inspection and debugging
- ✅ Data export capabilities

## Next Steps

1. **Monitor cache performance** in production
2. **Tune cache settings** based on usage patterns
3. **Add more cache sources** as needed
4. **Implement cache warming** for common models
5. **Add cache analytics** for optimization

This caching system provides comprehensive visibility into the model card generation process, enabling effective debugging and optimization of incomplete model cards.
