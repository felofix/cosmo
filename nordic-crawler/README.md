# Nordic Immigration Guide Crawler

A web crawler designed to extract immigration information from the Nordic Council's website, specifically focused on the guide for moving to Norway. The crawler uses crawl4ai and processes the data into a format suitable for RAG (Retrieval-Augmented Generation) systems.

## Features

- Crawls the Nordic Council's immigration guide
- Extracts structured content including headings and sections
- Processes data into RAG-friendly format
- Saves both raw and processed data in JSON format

## Installation

1. Make sure you have Python 3.10 or higher installed
2. Install Poetry if you haven't already:
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```
3. Install dependencies:
   ```bash
   poetry install
   ```

## Usage

Run the crawler using Poetry:

```bash
poetry run crawl
```

The crawler will:
1. Fetch content from https://www.norden.org/en/info-norden/guide-moving-norway
2. Process and structure the content
3. Save two JSON files in the `output` directory:
   - `norway_immigration_guide.json`: Raw extracted content
   - `norway_immigration_guide_rag.json`: Processed content ready for RAG systems

## Output Format

The RAG-formatted output includes:
- Document title
- Section heading
- Section content
- Source URL
- Metadata (type, country, section)

Run with 
```bash
poetry run python -m nordic_crawler.main --domains norden.org udi.no skatteetaten.no norway.no lifeinnorway.net lawyersnorway.eu politiet.no regjeringen.no une.no --output-format json --output-filename nordic_all
```

norden.org udi.no skatteetaten.no norway.no lifeinnorway.net lawyersnorway.eu politiet.no regjeringen.no une.no