from flask import Flask, jsonify, request, send_file, Response
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re
import os
import asyncio
import edge_tts
import tempfile

app = Flask(__name__)
CORS(app)

BASE_URL = "https://freewebnovel.com/weakest-beast-tamer-gets-all-sss-dragons"

# Default voice — Guy Neural (male narrator)
DEFAULT_VOICE = "en-US-GuyNeural"

NOISE_PATTERNS = [
    r'freewebnovel', r'novel\s*live', r'read.*online.*free',
    r'thank\s*you\s*for\s*(reading|visiting)',
    r'please\s*(support|visit|follow)',
    r'don\'t\s*forget\s*to',
    r'leave\s*a\s*(comment|review|rating)',
    r'advertisement', r'all\s*rights\s*reserved',
    r'copyright', r'discord', r'patreon',
    r'subscribe', r'report\s*(error|mistake)',
    r'share\s*(this|novel)',
    r'read\s*at', r'translator',
    r'use\s*(wasd|arrow\s*keys)',
    r'prev(ious)?\s*chapter',
    r'next\s*chapter',
    r'chapter\s*list',
    r'^\d+$',
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
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Cache-Control': 'max-age=0',
        'Referer': 'https://www.google.com/',
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


async def text_to_speech(text, voice=DEFAULT_VOICE):
    """Convert text to MP3 using Edge TTS"""
    tmp = tempfile.NamedTemporaryFile(
        delete=False, suffix='.mp3'
    )
    tmp.close()
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(tmp.name)
    return tmp.name


@app.route('/')
def serve_player():
    player_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'player.html'
    )
    return send_file(player_path)


@app.route('/manifest.json')
def serve_manifest():
    manifest_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'manifest.json'
    )
    return send_file(
        manifest_path,
        mimetype='application/manifest+json'
    )


@app.route('/chapter/<int:chapter_num>')
def get_chapter(chapter_num):
    data, error = fetch_chapter(chapter_num)
    if error:
        return jsonify({'error': error}), 404
    return jsonify(data)


@app.route('/speak', methods=['POST'])
def speak():
    """Convert paragraph text to MP3 audio"""
    try:
        body = request.get_json()
        text = body.get('text', '')
        voice = body.get('voice', DEFAULT_VOICE)
        if not text:
            return jsonify({'error': 'No text provided'}), 400
        # Limit text length per request
        text = text[:2000]
        # Run async TTS
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        mp3_path = loop.run_until_complete(
            text_to_speech(text, voice)
        )
        loop.close()
        def generate():
            with open(mp3_path, 'rb') as f:
                data = f.read(4096)
                while data:
                    yield data
                    data = f.read(4096)
            os.unlink(mp3_path)
        return Response(
            generate(),
            mimetype='audio/mpeg',
            headers={
                'Content-Disposition': 'inline',
                'Cache-Control': 'no-cache',
                'Access-Control-Allow-Origin': '*',
            }
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/ping')
def ping():
    return jsonify(
        {'status': 'Sovereign StoryForge running'}
    )


port = int(os.environ.get('PORT', 8080))

if __name__ == '__main__':
    print("Sovereign StoryForge Server")
    print(f"Running on http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
