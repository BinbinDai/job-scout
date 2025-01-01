# Job Scout

An automated job search tool that scrapes job listings from various tech companies.

## Features

- Scrapes job listings from multiple companies (Waymo, StackAV, NVIDIA, Scale, Databricks)
- Filters for specific job levels (Staff/L6) and roles (Software Engineer, Tech Lead Manager)
- Special handling for Autonomous Vehicle (AV) industry positions
- Supports different job board APIs (Greenhouse, Workday)
- Saves results to CSV file for easy viewing

## Requirements

```bash
pip install -r requirements.txt
```

## Usage

```bash
python job_openings.py
```

The script will:
1. Scrape job listings from configured companies
2. Filter based on specified criteria
3. Save matching positions to `job_openings.csv`

## Project Structure

- `job_openings.py`: Main script for job scraping
- `requirements.txt`: Python dependencies
- `learning_notes.md`: Documentation of development experience
- `job_openings.csv`: Output file containing matching job positions

## Development Notes

See `learning_notes.md` for detailed documentation of the development process and lessons learned while building this tool using Cursor Agent. 