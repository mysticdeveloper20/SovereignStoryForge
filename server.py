from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re
import os

app = Flask(__name__)
CORS(app)

BASE_URL = "https://freewebnovel.com/weakest-beast-tamer-gets-all-sss-dragons"

NOISE_PATTERNS = [
    r'freewebnovel', r'novel\s*live', r'novellive',
    r'read.*online.*free',
    r'thank\s*you\s*for\s*(reading|visiting)',
    r'please\s*(support|visit|follow)',
    r'don\'t\s*forget\s*to',
    r'leave\s*a\s*(comment|review|rating)',
    r'advertisement', r'all\s*rights\s*reserved',
    r'copyright', r'discord', r'patreon',
    r'subscribe', r'report\s*(error|mistake)',
    r'share\s*(this|novel)',
    r'read\s*at', r'translator',
]

def clean_text(text):
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        line = line.strip()
        if not line or len(line) < 3:
            continue
        is_noise = any(
            re.search(p, line, re.IGNORECASE)
            for p in NOISE_PATTERNS
        )
        if not is_noise:
            cleaned.append(line)
    return cleaned

def fetch_chapter(chapter_num):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Referer': 'https://freewebnovel.com/',
    }
    try:
        chapter_url = f"{BASE_URL}/chapter-{chapter_num}.html"
        response = requests.get(
            chapter_url, headers=headers, timeout=15
        )
        if response.status_code != 200:
            return None, f"Chapter {chapter_num} not found"
        soup = BeautifulSoup(response.text, 'html.parser')
        title = ''
        title_el = soup.find('h1') or soup.find('h2')
        if title_el:
            title = title_el.get_text().strip()
        content = soup.find('div', {'class': 'txt'})
        if not content:
            content = soup
        paragraphs = content.find_all('p')
        text = '\n'.join(
            p.get_text() for p in paragraphs
        ) if paragraphs else content.get_text('\n')
        lines = clean_text(text)
        final_paragraphs = []
        current = ''
        for line in lines:
            if len(line) > 150:
                if current:
                    final_paragraphs.append(current.strip())
                    current = ''
                final_paragraphs.append(line)
            else:
                current += ' ' + line
                if (
                    current.strip().endswith(
                        ('.', '!', '?', '...', '"')
                    ) and len(current) > 60
                ):
                    final_paragraphs.append(current.strip())
                    current = ''
        if current.strip():
            final_paragraphs.append(current.strip())
        final_paragraphs = [
            p for p in final_paragraphs if len(p) > 15
        ]
        return {
            'title': title or f'Chapter {chapter_num}',
            'chapter': chapter_num,
            'paragraphs': final_paragraphs,
            'total': len(final_paragraphs)
        }, None
    except Exception as e:
        return None, str(e)


@app.route('/')
def serve_player():
    player_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'player.html'
    )
    return send_file(player_path)


@app.route('/chapter/<int:chapter_num>')
def get_chapter(chapter_num):
    data, error = fetch_chapter(chapter_num)
    if error:
        return jsonify({'error': error}), 404
    return jsonify(data)


@app.route('/ping')
def ping():
    return jsonify(
        {'status': 'Sovereign StoryForge running'}
    )


if __name__ == '__main__':
    print("Sovereign StoryForge Server")
    print("Running on http://localhost:8080")
    port = int(os.environ.get('PORT', 8080))
app.run(host='0.0.0.0', port=port, debug=False)
