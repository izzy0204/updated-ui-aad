# AI Model Card Generator

A comprehensive system for generating professional model cards for dermatology AI models, featuring automated source discovery, AI-powered content analysis, and CHAI schema compliance.

## 🏗️ Project Structure

```
aad-model-card-generator/
├── src/
│   ├── core/                    # Core application files
│   │   ├── app.py              # Main Streamlit application
│   │   ├── app_simple.py       # Simplified version
│   │   ├── chai_schema.py      # CHAI schema definitions
│   │   └── walkthrough_demo.py # Demo script
│   ├── pipelines/              # Data processing pipelines
│   │   ├── cardgen_pipeline.py # Main card generation pipeline
│   │   └── model_card_pipeline.py # Model card processing
│   ├── ai_extractors/          # AI-powered content extraction
│   │   └── ai_extractor.py     # Gemini AI integration
│   ├── scrapers/               # Web scraping components
│   │   ├── robust_scraper_v2.py # Production-grade scraper
│   │   ├── scraping.py         # Basic scraping utilities
│   │   └── source_discovery_engine.py # Source discovery
│   └── utils/                  # Utility modules
│       ├── utils.py            # General utilities
│       ├── discovery.py        # Content discovery
│       ├── enhanced_publication_finder.py # Publication search
│       ├── citation_system.py  # Citation management
│       ├── field_mapping.py    # Schema field mapping
│       ├── consistency_enhancements.py # Data consistency
│       ├── targeted_questions.py # Question generation
│       └── result_cache.py     # Caching system
├── config/                     # Configuration files
│   └── config.py              # Application configuration
├── docs/                      # Documentation
│   ├── README_scraper.md      # Scraper documentation
│   └── replit.md             # Replit setup guide
├── assets/                    # Static assets
│   └── attached_assets/       # Project assets
├── tests/                     # Test files
├── pyproject.toml            # Project dependencies
└── uv.lock                   # Lock file
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Google Gemini API key
- Required dependencies (see `pyproject.toml`)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/aad-model-card-generator.git
cd aad-model-card-generator
```

2. Install dependencies:
```bash
pip install -e .
```

3. Set up environment variables:
```bash
export GEMINI_API_KEY="your_gemini_api_key_here"
```

4. Run the application:
```bash
streamlit run src/core/app.py --server.port 5000
```

## 📋 Features

### Core Capabilities
- **Automated Source Discovery**: Multi-platform content discovery from 15+ sources
- **AI-Powered Analysis**: Gemini AI integration for bias detection and compliance
- **CHAI Schema Compliance**: Full compliance with HTI-1 and 45 CFR 170.315 standards
- **Professional Output**: Comprehensive model cards with 80+ fields
- **Multiple Export Formats**: JSON, Markdown, and XML export options

### Web Scraping
- **Production-Grade Scraper**: Asynchronous architecture with robust error handling
- **Medical Domain Awareness**: Specialized rate limiting for medical websites
- **Content Extraction**: Advanced HTML parsing with noise removal
- **PDF Processing**: Text extraction from PDF documents
- **Compliance Features**: Robots.txt compliance and ethical scraping

### Data Processing
- **Pipeline Architecture**: Modular data processing pipelines
- **Caching System**: Intelligent result caching for performance
- **Consistency Enhancements**: Data validation and consistency checks
- **Citation Management**: Automated citation extraction and formatting

## 🔧 Configuration

The application uses environment variables for configuration:

- `GEMINI_API_KEY`: Required for AI-powered content analysis
- `GEMINI_MODEL`: Model to use (default: "gemini-1.5-pro")
- `GEMINI_TEMPERATURE`: Temperature setting (default: 0.2)

## 📖 Usage

### Web Interface

1. Navigate to the Streamlit application
2. Enter model name and optional developer name
3. Click "Generate Model Card"
4. View results in the Output tab
5. Export in your preferred format

### Programmatic Usage

```python
from src.pipelines.cardgen_pipeline import CardGenPipeline

# Initialize pipeline
pipeline = CardGenPipeline()

# Generate model card
result = await pipeline.generate_model_card(
    model_name="Your Model Name",
    developer_name="Developer Organization"
)

print(result)
```

## 🧪 Testing

Run the test suite:

```bash
pytest tests/ -v
```

## 📚 Documentation

- [Scraper Documentation](docs/README_scraper.md) - Detailed scraper features and API
- [Replit Setup Guide](docs/replit.md) - Setup instructions for Replit

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## 📄 License

This project is designed for dermatology AI model-card generation. Please ensure compliance with website terms of service and robots.txt when scraping external content.

## 🆘 Support

For issues and questions:
1. Check the documentation in the `docs/` directory
2. Review existing issues on GitHub
3. Create a new issue with detailed information

## 🔄 Recent Updates

- Organized project structure for better maintainability
- Separated concerns into logical modules
- Enhanced documentation and configuration management
- Improved code organization and readability
