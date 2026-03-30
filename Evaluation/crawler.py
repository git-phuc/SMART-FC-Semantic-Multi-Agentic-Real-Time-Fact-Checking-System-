import requests
from bs4 import BeautifulSoup
import csv
import os
import time

# List of categories from web-craw.txt
CATEGORIES_FILE = "e:/Research/Code/NCKH/Multi-Agentic/Evaluation/web-craw.txt"
OUTPUT_FILE = "e:/Research/Code/NCKH/Multi-Agentic/Evaluation/dataset.csv"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

def get_article_links(category_url, limit=10):
    print(f"Fetching category: {category_url}", flush=True)
    try:
        response = requests.get(category_url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        links = []
        # Find all <a> tags that have a link ending in .htm and containing a digit sequence (article ID)
        for a in soup.find_all('a', href=True):
            href = a['href']
            # Normalize URL
            if href.startswith('/'):
                href = "https://baochinhphu.vn" + href
            
            # Simple heuristic for article links: ends with .htm and has a long ID at the end
            # AND skip theme/topic aggregator pages (containing /chu-de/)
            if href.endswith('.htm') and any(char.isdigit() for char in href.split('/')[-1]) and "/chu-de/" not in href:
                # Avoid category links (usually short slugs)
                if href not in links and href != category_url:
                    links.append(href)
            
            if len(links) >= limit:
                break
        return links
    except Exception as e:
        print(f"Error fetching category {category_url}: {e}")
        return []

def scrape_article(url):
    print(f"Scraping article: {url}", flush=True)
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or "utf-8"
        soup = BeautifulSoup(response.text, 'html.parser')
        
        title = soup.title.string.replace("- .: VGP News :. BÁO ĐIỆN TỬ CHÍNH PHỦ NƯỚC CHXHCN VIỆT NAM", "").strip() if soup.title else "N/A"
        
        # Look for content in common selectors for baochinhphu
        # Based on web_scraper.py logic
        content_div = soup.find('div', {'class': 'detail-content'}) or \
                      soup.find('div', {'id': 'content'}) or \
                      soup.find('div', {'class': 'article-body'})
        
        if not content_div:
            # Fallback to article or main
            content_div = soup.find('article') or soup.find('main')
            
        if content_div:
            # Extract paragraphs
            paragraphs = content_div.find_all('p')
            text = "\n\n".join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 20])
        else:
            text = "Content not found"
            
        return {
            "title": title,
            "content": text,
            "url": url,
            "label": "THẬT" # Default label for government news
        }
    except Exception as e:
        print(f"Error scraping article {url}: {e}")
        return None

def main():
    if not os.path.exists(CATEGORIES_FILE):
        print(f"File not found: {CATEGORIES_FILE}")
        return

    with open(CATEGORIES_FILE, 'r', encoding='utf-8') as f:
        categories = [line.strip() for line in f if line.strip() and line.strip().startswith('http')]

    data = []
    idx = 1
    
    for cat in categories:
        links = get_article_links(cat, limit=10)
        for link in links:
            article_data = scrape_article(link)
            if article_data:
                data.append({
                    "index": idx,
                    "title": article_data["title"],
                    "nội dung": article_data["content"],
                    "Link bài viết": article_data["url"],
                    "label": article_data["label"]
                })
                idx += 1
            time.sleep(1) # Be polite
    
    # Save to CSV
    keys = ["index", "title", "nội dung", "Link bài viết", "label"]
    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8-sig') as f:
        dict_writer = csv.DictWriter(f, fieldnames=keys)
        dict_writer.writeheader()
        dict_writer.writerows(data)
    
    print(f"Successfully saved {len(data)} samples to {OUTPUT_FILE}", flush=True)

if __name__ == "__main__":
    main()
