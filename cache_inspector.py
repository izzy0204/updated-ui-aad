#!/usr/bin/env python3
"""
Cache Inspector Tool for Model Card Generation

This tool provides comprehensive inspection and debugging capabilities for the
caching system used in model card generation. It allows you to:

1. View cache statistics and performance metrics
2. Inspect cached data by model name, source, or stage
3. Export cached data for analysis
4. Clear cache for specific models
5. Debug why model cards aren't being fully filled out

Usage:
    python cache_inspector.py --model "Derm Foundation" --developer "Google Health"
    python cache_inspector.py --stats
    python cache_inspector.py --export "Derm Foundation" --output cache_export.json
    python cache_inspector.py --clear "Derm Foundation"
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from utils.cache_system import get_cache, CacheSystem

class CacheInspector:
    """Interactive cache inspection and debugging tool"""
    
    def __init__(self, cache_dir: str = "cache"):
        self.cache = CacheSystem(cache_dir)
    
    async def show_stats(self):
        """Display comprehensive cache statistics"""
        print(" CACHE STATISTICS")
        print("=" * 50)
        
        stats = await self.cache.get_stats()
        
        print(f"Total Entries: {stats['total_entries']}")
        print(f"Cache Hits: {stats['hits']}")
        print(f"Cache Misses: {stats['misses']}")
        print(f"Hit Rate: {stats['hit_rate']:.2%}")
        print(f"Evictions: {stats['evictions']}")
        print(f"Memory Cache Size: {stats['memory_cache_size']}")
        print(f"Last Cleanup: {stats['last_cleanup'] or 'Never'}")
        
        # Show breakdown by source
        print("\n BREAKDOWN BY SOURCE")
        print("-" * 30)
        
        sources = ["web_search", "web_fetch", "model_sources", "gemini_planning", "gemini_extraction", "gemini_validation"]
        for source in sources:
            entries = await self.cache.inspect_by_source(source)
            print(f"{source}: {len(entries)} entries")
    
    async def inspect_model(self, model_name: str, developer: str = ""):
        """Inspect all cached data for a specific model"""
        print(f" INSPECTING CACHE FOR MODEL: {model_name}")
        if developer:
            print(f"Developer: {developer}")
        print("=" * 60)
        
        # Get all cached data for this model
        cached_data = await self.cache.inspect_by_model(model_name)
        
        if not cached_data:
            print(" No cached data found for this model")
            return
        
        total_entries = sum(len(entries) for entries in cached_data.values())
        print(f" Total cached entries: {total_entries}")
        
        # Show breakdown by source
        print("\n BREAKDOWN BY SOURCE:")
        print("-" * 40)
        for source, entries in cached_data.items():
            print(f"{source}: {len(entries)} entries")
            
            # Show recent entries for each source
            if entries:
                print(f"  Recent entries:")
                for entry in entries[:3]:  # Show top 3
                    timestamp = entry['timestamp']
                    url = entry.get('url', 'N/A')
                    stage = entry.get('stage', 'N/A')
                    print(f"    - {timestamp}: {url} (stage: {stage})")
                if len(entries) > 3:
                    print(f"    ... and {len(entries) - 3} more")
                print()
    
    async def inspect_source(self, source: str):
        """Inspect all cached data from a specific source"""
        print(f" INSPECTING CACHE FOR SOURCE: {source}")
        print("=" * 50)
        
        entries = await self.cache.inspect_by_source(source)
        
        if not entries:
            print(" No cached data found for this source")
            return
        
        print(f" Total entries: {len(entries)}")
        
        # Group by model
        models = {}
        for entry in entries:
            model = entry.get('model_name', 'Unknown')
            if model not in models:
                models[model] = []
            models[model].append(entry)
        
        print(f"\n BREAKDOWN BY MODEL:")
        print("-" * 30)
        for model, model_entries in models.items():
            print(f"{model}: {len(model_entries)} entries")
    
    async def export_model_data(self, model_name: str, output_path: Optional[str] = None):
        """Export all cached data for a model to a JSON file"""
        print(f" EXPORTING CACHE DATA FOR MODEL: {model_name}")
        print("=" * 50)
        
        output_file = await self.cache.export_cache_data(model_name, Path(output_path) if output_path else None)
        
        print(f" Export completed: {output_file}")
        print(f" File size: {output_file.stat().st_size / 1024:.1f} KB")
        
        # Show summary of exported data
        with open(output_file, 'r', encoding='utf-8') as f:
            export_data = json.load(f)
        
        print(f"\n EXPORT SUMMARY:")
        print(f"Model: {export_data['model_name']}")
        print(f"Export timestamp: {export_data['export_timestamp']}")
        print(f"Sources exported: {len(export_data['cached_data'])}")
        
        for source, entries in export_data['cached_data'].items():
            print(f"  {source}: {len(entries)} entries")
    
    async def clear_model_cache(self, model_name: str):
        """Clear all cached data for a specific model"""
        print(f"  CLEARING CACHE FOR MODEL: {model_name}")
        print("=" * 50)
        
        # First show what will be deleted
        cached_data = await self.cache.inspect_by_model(model_name)
        total_entries = sum(len(entries) for entries in cached_data.values())
        
        if total_entries == 0:
            print(" No cached data found for this model")
            return
        
        print(f"  This will delete {total_entries} cache entries:")
        for source, entries in cached_data.items():
            print(f"  {source}: {len(entries)} entries")
        
        # Confirm deletion
        confirm = input("\n Are you sure you want to proceed? (yes/no): ")
        if confirm.lower() in ['yes', 'y']:
            await self.cache.clear_model_cache(model_name)
            print(" Cache cleared successfully")
        else:
            print(" Operation cancelled")
    
    async def debug_missing_fields(self, model_name: str, developer: str = ""):
        """Debug why model cards aren't being fully filled out"""
        print(f" DEBUGGING MISSING FIELDS FOR MODEL: {model_name}")
        if developer:
            print(f"Developer: {developer}")
        print("=" * 60)
        
        # Get all cached data for this model
        cached_data = await self.cache.inspect_by_model(model_name)
        
        if not cached_data:
            print(" No cached data found for this model")
            print(" Try running the model card generation first")
            return
        
        print(" ANALYSIS OF CACHED DATA:")
        print("-" * 40)
        
        # Analyze web search results
        web_search_entries = cached_data.get('web_search', [])
        if web_search_entries:
            print(f" Web Search Results: {len(web_search_entries)} queries cached")
            for entry in web_search_entries[:3]:
                metadata = entry.get('metadata', {})
                query = metadata.get('query', 'Unknown')
                results_count = metadata.get('max_results', 0)
                print(f"  - Query: '{query}' -> {results_count} results")
        else:
            print(" No web search results found")
        
        # Analyze web fetch results
        web_fetch_entries = cached_data.get('web_fetch', [])
        failed_fetches = 0
        successful_fetches = []
        if web_fetch_entries:
            successful_fetches = [e for e in web_fetch_entries if e.get('metadata', {}).get('status', 0) == 200]
            failed_fetches = len(web_fetch_entries) - len(successful_fetches)
            print(f" Web Fetch Results: {len(web_fetch_entries)} URLs processed")
            print(f"  - Successful: {len(successful_fetches)}")
            print(f"  - Failed: {failed_fetches}")
            
            if failed_fetches > 0:
                print("    Some URLs failed to fetch - this could cause missing information")
        else:
            print(" No web fetch results found")
        
        # Analyze Gemini extraction results
        extraction_entries = cached_data.get('gemini_extraction', [])
        if extraction_entries:
            print(f" Gemini Extraction Results: {len(extraction_entries)} extractions cached")
            for entry in extraction_entries[:3]:
                metadata = entry.get('metadata', {})
                field_paths = metadata.get('field_paths', [])
                sources_length = metadata.get('sources_length', 0)
                print(f"  - Fields: {field_paths} (sources: {sources_length} chars)")
        else:
            print(" No Gemini extraction results found")
        
        # Analyze model sources
        model_sources_entries = cached_data.get('model_sources', [])
        if model_sources_entries:
            print(f" Model Sources: {len(model_sources_entries)} source lists cached")
            for entry in model_sources_entries:
                metadata = entry.get('metadata', {})
                found_count = metadata.get('found_count', 0)
                query_count = metadata.get('query_count', 0)
                print(f"  - Queries: {query_count}, Sources found: {found_count}")
        else:
            print(" No model sources found")
        
        print("\n RECOMMENDATIONS:")
        print("-" * 20)
        
        if not web_search_entries:
            print("• Run web search queries to find model information")
        if not web_fetch_entries:
            print("• Fetch content from discovered URLs")
        if not extraction_entries:
            print("• Run Gemini extraction on gathered content")
        if failed_fetches > 0:
            print("• Check failed URL fetches - some sources may be inaccessible")
        if len(successful_fetches) < 3:
            print("• Consider adding more seed URLs or improving search queries")
        
        print("\n NEXT STEPS:")
        print("1. Check the exported cache data for detailed analysis")
        print("2. Verify that search queries are finding relevant sources")
        print("3. Ensure URLs are accessible and returning useful content")
        print("4. Review Gemini extraction results for completeness")

async def main():
    parser = argparse.ArgumentParser(description="Cache Inspector for Model Card Generation")
    parser.add_argument("--model", help="Model name to inspect")
    parser.add_argument("--developer", help="Developer name")
    parser.add_argument("--source", help="Source to inspect (web_search, web_fetch, gemini_extraction, etc.)")
    parser.add_argument("--stats", action="store_true", help="Show cache statistics")
    parser.add_argument("--export", help="Export cached data for a model")
    parser.add_argument("--output", help="Output file for export")
    parser.add_argument("--clear", help="Clear cache for a model")
    parser.add_argument("--debug", help="Debug missing fields for a model")
    parser.add_argument("--cache-dir", default="cache", help="Cache directory to use")
    
    args = parser.parse_args()
    
    inspector = CacheInspector(args.cache_dir)
    
    if args.stats:
        await inspector.show_stats()
    elif args.model:
        await inspector.inspect_model(args.model, args.developer or "")
    elif args.source:
        await inspector.inspect_source(args.source)
    elif args.export:
        await inspector.export_model_data(args.export, args.output)
    elif args.clear:
        await inspector.clear_model_cache(args.clear)
    elif args.debug:
        await inspector.debug_missing_fields(args.debug, args.developer or "")
    else:
        print(" Please specify an action. Use --help for options.")

if __name__ == "__main__":
    asyncio.run(main())
