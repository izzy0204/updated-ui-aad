#!/usr/bin/env python3
"""
Test Script for Caching System with Derm Foundation Model

This script tests the caching system by running model card generation
for the Derm Foundation model with Google Health as the developer.
It demonstrates how the caching system captures and stores all scraped
and extracted information for debugging purposes.

Usage:
    python test_caching.py
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from utils.cache_system import get_cache, cache_context
from agents.gemini_agent.agent import run_async
from utils.web_search import discover_and_fetch, web_search
from scrapers.robust_scraper_v2 import RobustWebScraper

async def test_web_search_caching():
    """Test web search caching"""
    print("🔍 Testing Web Search Caching...")
    
    cache = get_cache()
    
    # Test search queries
    queries = [
        "Derm Foundation Google Health",
        "Derm Foundation dermatology AI",
        "Derm Foundation model card"
    ]
    
    for query in queries:
        print(f"  Searching: {query}")
        results = await web_search(query, max_results=5)
        print(f"    Found {len(results)} results")
        
        # Check if results were cached
        cached_results = await cache.get("web_search", query, max_results=5)
        if cached_results:
            print(f"    ✅ Results cached successfully")
        else:
            print(f"    ❌ Results not cached")
    
    print()

async def test_model_sources_caching():
    """Test model sources discovery caching"""
    print("🔍 Testing Model Sources Caching...")
    
    cache = get_cache()
    
    model_name = "Derm Foundation"
    developer = "Google Health"
    
    print(f"  Discovering sources for: {model_name} ({developer})")
    
    # This should use the cached web search results
    sources = await discover_and_fetch(model_name, developer, top_k=3)
    discovered, pages = sources
    
    print(f"    Discovered {len(discovered)} sources")
    print(f"    Fetched {len(pages)} pages")
    
    # Check if sources were cached
    cache_key = f"{model_name}_{developer}"
    cached_sources = await cache.get("model_sources", cache_key)
    if cached_sources:
        print(f"    ✅ Sources cached successfully")
    else:
        print(f"    ❌ Sources not cached")
    
    print()

async def test_robust_scraper_caching():
    """Test robust scraper caching"""
    print("🔍 Testing Robust Scraper Caching...")
    
    cache = get_cache()
    scraper = RobustWebScraper()
    
    # Test URLs
    test_urls = [
        "https://www.google.com",
        "https://github.com",
        "https://huggingface.co"
    ]
    
    for url in test_urls:
        print(f"  Scraping: {url}")
        result = await scraper.extract_content_from_url(url, model_name="Derm Foundation")
        
        print(f"    Status: {result.get('status', 'unknown')}")
        print(f"    Text length: {len(result.get('clean_text', ''))}")
        
        # Check if result was cached
        cached_result = await cache.get("robust_scraper", url)
        if cached_result:
            print(f"    ✅ Result cached successfully")
        else:
            print(f"    ❌ Result not cached")
    
    print()

async def test_gemini_agent_caching():
    """Test Gemini agent caching"""
    print("🔍 Testing Gemini Agent Caching...")
    
    cache = get_cache()
    
    model_name = "Derm Foundation"
    developer = "Google Health"
    
    print(f"  Running Gemini agent for: {model_name} ({developer})")
    
    try:
        # Run the agent with limited iterations for testing
        agent_result, citations = await run_async(
            model_hint=f"{model_name} ({developer})",
            max_iters=1,  # Limited for testing
            coverage_target=0.3,  # Lower threshold for testing
            developer=developer,
            seed_urls=["https://www.google.com"]  # Simple seed URL
        )
        
        print(f"    Agent completed successfully")
        print(f"    Citations: {len(citations)}")
        
        # Check if planning was cached
        cache_key = f"{model_name} ({developer})_{developer}"
        cached_plan = await cache.get("gemini_planning", cache_key)
        if cached_plan:
            print(f"    ✅ Planning cached successfully")
        else:
            print(f"    ❌ Planning not cached")
        
        # Check if extractions were cached
        extraction_entries = await cache.inspect_by_source("gemini_extraction")
        if extraction_entries:
            print(f"    ✅ {len(extraction_entries)} extractions cached")
        else:
            print(f"    ❌ No extractions cached")
            
    except Exception as e:
        print(f"    ❌ Agent failed: {e}")
    
    print()

async def test_cache_inspection():
    """Test cache inspection capabilities"""
    print("🔍 Testing Cache Inspection...")
    
    cache = get_cache()
    
    # Show cache stats
    stats = await cache.get_stats()
    print(f"  Cache Statistics:")
    print(f"    Total entries: {stats['total_entries']}")
    print(f"    Hits: {stats['hits']}")
    print(f"    Misses: {stats['misses']}")
    print(f"    Hit rate: {stats['hit_rate']:.2%}")
    
    # Inspect by model
    model_data = await cache.inspect_by_model("Derm Foundation")
    if model_data:
        print(f"  Model 'Derm Foundation' has cached data:")
        for source, entries in model_data.items():
            print(f"    {source}: {len(entries)} entries")
    else:
        print(f"  No cached data found for 'Derm Foundation'")
    
    print()

async def test_cache_export():
    """Test cache export functionality"""
    print("🔍 Testing Cache Export...")
    
    cache = get_cache()
    
    model_name = "Derm Foundation"
    
    try:
        export_file = await cache.export_cache_data(model_name)
        print(f"  ✅ Export completed: {export_file}")
        
        # Check file size
        file_size_kb = export_file.stat().st_size / 1024
        print(f"  📁 Export file size: {file_size_kb:.1f} KB")
        
    except Exception as e:
        print(f"  ❌ Export failed: {e}")
    
    print()

async def main():
    """Main test function"""
    print("🚀 TESTING CACHING SYSTEM FOR DERM FOUNDATION MODEL")
    print("=" * 60)
    print()
    
    # Use cache context to ensure clean state
    async with cache_context("test_cache") as cache:
        print(f"📁 Using cache directory: {cache.cache_dir}")
        print()
        
        # Run all tests
        await test_web_search_caching()
        await test_model_sources_caching()
        await test_robust_scraper_caching()
        await test_gemini_agent_caching()
        await test_cache_inspection()
        await test_cache_export()
        
        print("✅ ALL TESTS COMPLETED")
        print()
        
        # Final cache stats
        final_stats = await cache.get_stats()
        print("📊 FINAL CACHE STATISTICS:")
        print(f"  Total entries: {final_stats['total_entries']}")
        print(f"  Cache hits: {final_stats['hits']}")
        print(f"  Cache misses: {final_stats['misses']}")
        print(f"  Hit rate: {final_stats['hit_rate']:.2%}")
        print(f"  Memory cache size: {final_stats['memory_cache_size']}")
        
        print()
        print("💡 NEXT STEPS:")
        print("1. Use cache_inspector.py to inspect cached data:")
        print("   python cache_inspector.py --model 'Derm Foundation' --developer 'Google Health'")
        print("2. Export cache data for analysis:")
        print("   python cache_inspector.py --export 'Derm Foundation' --output derm_foundation_cache.json")
        print("3. Debug missing fields:")
        print("   python cache_inspector.py --debug 'Derm Foundation' --developer 'Google Health'")

if __name__ == "__main__":
    asyncio.run(main())
