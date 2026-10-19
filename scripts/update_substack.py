"""Refresh substack.json and the pre-rendered Substack posts in index.html and insights.html.

Run by the GitHub Action in .github/workflows/substack.yml. Uses only the Python standard library.
"""
import html, json, re, sys, urllib.request
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUB = 'https://wiweck.substack.com'
UA = {'User-Agent': 'Mozilla/5.0 (compatible; TriImpactSite/1.0)'}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read().decode('utf-8')


def from_archive():
    data = json.loads(get(PUB + '/api/v1/archive?sort=new&offset=0&limit=12'))
    keys = ['title', 'subtitle', 'description', 'canonical_url', 'post_date', 'cover_image', 'slug']
    return [{k: p.get(k) for k in keys} for p in data]


def from_rss():
    import xml.etree.ElementTree as ET
    root = ET.fromstring(get(PUB + '/feed'))
    out = []
    for item in root.iter('item'):
        enc = item.find('enclosure')
        date = item.findtext('pubDate') or ''
        try:
            date = parsedate_to_datetime(date).isoformat()
        except Exception:
            pass
        out.append({'title': item.findtext('title'), 'subtitle': '', 'description': item.findtext('description'),
                    'canonical_url': item.findtext('link'), 'post_date': date,
                    'cover_image': enc.get('url') if enc is not None else '', 'slug': ''})
    return out[:12]


def esc(s):
    return html.escape(str(s or ''), quote=True).replace('&#x27;', '&#039;')


def strip(s):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html.unescape(str(s or '')))).strip()


def fdate(s):
    try:
        d = datetime.fromisoformat(str(s).replace('Z', '+00:00'))
        return f'{d.day} {d.strftime("%b")} {d.year}'
    except Exception:
        return 'Substack article'


def image(p):
    img = p.get('cover_image') or ''
    if 'substack-post-media.s3.amazonaws.com' in img:
        img = 'https://substackcdn.com/image/fetch/w_1200,h_675,c_fill,f_auto,q_auto:good,fl_progressive:steep/' + urllib.parse.quote(img, safe='')
    return img


def summary(p, n):
    return strip(p.get('description') or p.get('subtitle') or '')[:n] or 'Read the full practitioner analysis on The Sustainability Realist.'


def home_cards(posts):
    out = []
    for p in posts[:3]:
        img = image(p)
        media = (f'<div class="insight-card-media"><img src="{esc(img)}" alt="Thumbnail image from the Substack article {esc(p["title"])}" loading="lazy"></div>'
                 if re.search(r'substackcdn\.com|substack-post-media', img) else
                 '<div class="insight-card-media insight-card-placeholder" aria-hidden="true"><span>SR</span></div>')
        u = esc(p['canonical_url'])
        out.append(f'<article class="insight-card">{media}<div class="insight-card-content"><div class="insight-meta">{esc(fdate(p["post_date"]))}</div>'
                   f'<h3><a href="{u}" target="_blank" rel="noopener">{esc(p["title"])}</a></h3><p>{esc(summary(p, 210))}</p>'
                   f'<a class="text-link" href="{u}" target="_blank" rel="noopener">Read insight <span class="arrow" aria-hidden="true">→</span></a></div></article>')
    return ''.join(out)


def journal_rows(posts):
    out = []
    for i, p in enumerate(posts[:9]):
        u = esc(p['canonical_url'])
        out.append(f'<div class="journal-row{" is-lead" if i == 0 else ""}"><time>{esc(fdate(p["post_date"]))}</time><div>'
                   f'<h3><a class="journal-row-link" href="{u}" target="_blank" rel="noopener">{esc(p["title"])}</a></h3><p>{esc(summary(p, 220))}</p>'
                   f'<a class="text-link" href="{u}" target="_blank" rel="noopener">Read insight <span class="arrow" aria-hidden="true">→</span></a></div></div>')
    return ''.join(out)


def splice(path, html_block):
    t = path.read_text(encoding='utf-8')
    new = re.sub(r'(<!-- substack:start -->)[\s\S]*?(<!-- substack:end -->)', lambda m: m.group(1) + html_block + m.group(2), t, count=1)
    if new != t:
        path.write_text(new, encoding='utf-8')


def main():
    import urllib.parse  # noqa: F401  (used in image())
    try:
        posts = from_archive()
    except Exception as e:
        print('archive failed, trying RSS:', e)
        posts = from_rss()
    posts = [p for p in posts if p.get('title') and p.get('canonical_url')]
    if not posts:
        sys.exit('No posts found; leaving files unchanged.')
    (ROOT / 'substack.json').write_text(json.dumps(posts, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    splice(ROOT / 'index.html', home_cards(posts))
    splice(ROOT / 'insights.html', journal_rows(posts))
    print(f'{len(posts)} posts written')


if __name__ == '__main__':
    import urllib.parse
    main()
