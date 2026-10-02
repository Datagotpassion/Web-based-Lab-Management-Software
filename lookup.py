"""Pull product details out of a supplier page, so a new reagent can be filled
in from its catalogue URL instead of typed out.

Standard library only, in keeping with the rest of the project -- no scraping
framework, no HTML parser dependency.

How much is recovered depends entirely on the vendor. Most large suppliers
publish schema.org Product data as JSON-LD, which gives name, catalogue number,
brand and description cleanly; the rest falls back to Open Graph tags, then to
the page title. Anything not found is simply left out rather than guessed at,
so the form is never silently filled with something wrong.

A browser User-Agent is required: several suppliers time out or refuse
non-browser clients outright.
"""

import ipaddress
import json
import re
import socket
import urllib.error
import urllib.parse
import urllib.request

# Several vendors stall indefinitely for non-browser clients.
USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/124.0 Safari/537.36')

TIMEOUT = 25
MAX_BYTES = 3 * 1024 * 1024

# Units as written on product pages, mapped to the ones this app stores.
UNIT_CANON = {
    'ug': 'µg', 'mcg': 'µg', 'µg': 'µg', 'mg': 'mg', 'g': 'g', 'ng': 'ng',
    'ml': 'mL', 'l': 'L', 'ul': 'µL', 'µl': 'µL',
    'mg/ml': 'mg/mL', 'ug/ml': 'µg/mL', 'µg/ml': 'µg/mL',
    'ng/ml': 'ng/mL', 'mm': 'mM', 'um': 'µM', 'µm': 'µM', 'nm': 'nM',
    'm': 'M', 'iu/ml': 'IU/mL', 'u/ml': 'U/mL',
}

# Deliberately NOT extracting concentration from prose.
#
# Product descriptions are full of potency figures -- "IC50 = 140 nM", "Kd of
# 1 uM" -- and pulling those in as a stock concentration produces a number that
# looks authoritative and is completely wrong. Someone would dilute from it.
# Leaving the field blank is strictly better, so concentration is only taken
# from an explicitly labelled field, never from free text.
LABELLED_CONCENTRATION = re.compile(
    r'(?:stock\s+)?concentration\s*[:=]\s*(\d+(?:\.\d+)?)\s*'
    r'(mg/mL|µg/mL|ug/mL|ng/mL|mM|µM|uM|nM|IU/mL|U/mL)\b', re.I)

# Values vendors use to mean "nothing here".
JUNK = {'-', '--', 'n/a', 'na', 'none', 'null', 'not applicable', ''}

# Catalogue numbers in pasted page text. Vendors label them differently --
# "Cat. No.", "Order no.", "Product Number", "Item #", "REF" -- so the label is
# matched loosely, with a shape-based fallback for grouped-digit numbers like
# Miltenyi's 130-109-386.
CATALOGUE_LABELLED = re.compile(
    r'\b(?:cat(?:alog|alogue)?|order|product|item|ref(?:erence)?)'
    # The label parts may be separated by spaces: "Cat. No.", "Product Number".
    r'(?:\s*(?:\.|no\.?|number|#))*\s*[:#]?\s*'
    r'([A-Za-z]{0,4}[-_]?\d{3,8}(?:[-_][A-Za-z0-9]{1,6})*)', re.I)
CATALOGUE_SHAPED = re.compile(r'\b(\d{3}-\d{3}-\d{3})\b')

# "Size: 25 ug", "Pack size 1 mg".
SIZE_LABELLED = re.compile(
    r'\b(?:pack\s*)?(?:size|quantity|amount)\s*[:=]?\s*'
    r'(\d+(?:\.\d+)?)\s*(µg|ug|mcg|mg|ng|g|µL|uL|mL|L)\b', re.I)

# Pack size, e.g. the 50UG in catalogue number 200-02-50UG.
PACK_SIZE = re.compile(r'(\d+(?:\.\d+)?)\s*(µg|ug|mcg|mg|ng|g|µL|uL|mL|L)\b', re.I)


class LookupError_(Exception):
    """A failure worth showing the user verbatim."""


def _check_public(url):
    """Refuse anything that is not a public http(s) address.

    The app has no authentication, so an endpoint that fetches arbitrary URLs
    would otherwise let anyone on the lab network use this machine to reach
    internal services it can see and they cannot.
    """
    parts = urllib.parse.urlparse(url)
    if parts.scheme not in ('http', 'https'):
        raise LookupError_('Only http and https addresses can be fetched.')
    if not parts.hostname:
        raise LookupError_('That does not look like a web address.')
    try:
        infos = socket.getaddrinfo(parts.hostname, None)
    except socket.gaierror:
        raise LookupError_(f'Could not resolve {parts.hostname}.')
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast):
            raise LookupError_('That address is on a private network.')


def fetch(url):
    _check_public(url)
    req = urllib.request.Request(url, headers={
        'User-Agent': USER_AGENT,
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'en-US,en;q=0.9',
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read(MAX_BYTES)
    except urllib.error.HTTPError as exc:
        raise LookupError_(f'The site returned {exc.code} ({exc.reason}).')
    except urllib.error.URLError as exc:
        raise LookupError_(f'Could not reach the site: {exc.reason}')
    except socket.timeout:
        raise LookupError_('The site did not respond in time.')
    return raw.decode('utf-8', 'replace')


def _unescape_literals(text):
    r"""Some pages double-escape their JSON, leaving a literal ® in the
    decoded string. Decode those rather than showing them to the user."""
    if not isinstance(text, str) or '\\u' not in text:
        return text
    try:
        return json.loads(f'"{text}"')
    except ValueError:
        return text


def _json_ld_products(html):
    for block in re.findall(r'<script[^>]+ld\+json[^>]*>(.*?)</script>',
                            html, re.S | re.I):
        try:
            data = json.loads(block.strip())
        except ValueError:
            continue
        for item in (data if isinstance(data, list) else [data]):
            if not isinstance(item, dict):
                continue
            # Some sites wrap everything in an @graph.
            for node in item.get('@graph', [item]):
                if isinstance(node, dict) and 'Product' in str(node.get('@type', '')):
                    yield node


def _meta(html, prop):
    m = re.search(
        rf'<meta[^>]+(?:property|name)=["\']{re.escape(prop)}["\'][^>]+'
        rf'content=["\']([^"\']*)["\']', html, re.I)
    return m.group(1).strip() if m else None


def _clean(text, limit=400):
    if not text:
        return None
    text = _unescape_literals(text)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    # Vendors put placeholders in these fields; a literal "-" as the supplier
    # is worse than an empty box, because it looks deliberate.
    if text.lower() in JUNK:
        return None
    return text[:limit] or None


def _is_vendor_name(name, host):
    """Is this just the company's own name rather than a product?

    Compared on letters alone, so "Miltenyi Biotec" matches the host
    miltenyibiotec.com.
    """
    squash = lambda s: re.sub(r'[^a-z]', '', s.lower())
    n, h = squash(name), squash(host.split('.')[0])
    return bool(n) and bool(h) and (n == h or n in h or h in n)


def _pack_size(*sources):
    """Pack size, e.g. '50 µg' from a catalogue number like 200-02-50UG."""
    for src in sources:
        if not src:
            continue
        m = PACK_SIZE.search(str(src))
        if m:
            unit = UNIT_CANON.get(m.group(2).lower(), m.group(2))
            return f'{m.group(1)} {unit}'
    return None


def _concentration(*sources):
    """Only an explicitly labelled concentration. See LABELLED_CONCENTRATION."""
    for src in sources:
        if not src:
            continue
        m = LABELLED_CONCENTRATION.search(str(src))
        if m:
            unit = UNIT_CANON.get(m.group(2).lower(), m.group(2))
            return float(m.group(1)), unit
    return None, None


def extract(url, html=None):
    """Return the fields worth pre-filling, plus a note on where they came from.

    Only keys that were actually found are present, so the caller can fill
    blanks without overwriting anything the user has already typed.
    """
    html = html if html is not None else fetch(url)
    found = {'product_url': url} if url else {}
    sources = []

    # Content pasted from a browser may be the page's text rather than its
    # source. There is no markup to mine, so take the first substantial line as
    # the name and look for a catalogue-shaped token.
    if '<' not in html[:2000]:
        lines = [l.strip() for l in html.splitlines() if l.strip()]
        if lines:
            found['drug_name'] = lines[0][:200]
            sources.append('pasted text')
        body = ' '.join(lines)
        m = CATALOGUE_LABELLED.search(body) or CATALOGUE_SHAPED.search(body)
        if m:
            found['product_number'] = m.group(1)
        size = SIZE_LABELLED.search(body)
        if size:
            unit = UNIT_CANON.get(size.group(2).lower(), size.group(2))
            found['aliquot_volume'] = f'{size.group(1)} {unit}'
        desc = next((l for l in lines[1:] if len(l) > 60), None)
        if desc:
            found['notes'] = desc[:400]
        conc, unit = _concentration(body)
        if conc is not None:
            found['stock_concentration'] = conc
            found['stock_unit'] = unit
        found['_sources'] = sources or ['pasted text']
        return found

    product = next(iter(_json_ld_products(html)), None)
    if product:
        sources.append('structured product data')
        name = _clean(product.get('name'), 200)
        if name:
            found['drug_name'] = name
        sku = product.get('sku') or product.get('mpn')
        if sku:
            found['product_number'] = _clean(str(sku), 60)

        brand = product.get('brand')
        if isinstance(brand, dict):
            brand = brand.get('name')
        maker = product.get('manufacturer')
        if isinstance(maker, dict):
            maker = maker.get('name')
        supplier = _clean(brand or maker, 80)
        if supplier:
            found['supplier'] = supplier

        description = _clean(product.get('description'))
        if description:
            found['notes'] = description

        conc, unit = _concentration(description, name)
        if conc is not None:
            found['stock_concentration'] = conc
            found['stock_unit'] = unit

        size = _pack_size(sku, name)
        if size:
            found['aliquot_volume'] = size

    host = re.sub(r'^www\.', '', urllib.parse.urlparse(url).hostname or '')

    # Fall back to the page's own metadata for anything still missing.
    if 'drug_name' not in found:
        title = _clean(_meta(html, 'og:title'), 200)
        if not title:
            m = re.search(r'<title[^>]*>(.*?)</title>', html, re.S | re.I)
            title = _clean(m.group(1), 200) if m else None
        if title:
            # Trim the vendor's own suffix: "Product | Thermo Fisher".
            name = re.split(r'\s+[|–—-]\s+', title)[0].strip()
            # A title that is only the vendor's name means the page did not
            # render a product -- usually it is built client-side. Taking it
            # would put the company name in as the reagent.
            if name and not _is_vendor_name(name, host):
                found['drug_name'] = name
                sources.append('page title')

    if 'notes' not in found:
        desc = _clean(_meta(html, 'og:description') or _meta(html, 'description'))
        if desc:
            found['notes'] = desc
            sources.append('page description')

    if 'supplier' not in found and host:
        found['supplier'] = host
        sources.append('web address')

    # A catalogue number is often the last numeric-ish segment of the URL, and
    # is worth having when the page itself gave nothing.
    if 'product_number' not in found:
        for seg in reversed(urllib.parse.urlparse(url).path.strip('/').split('/')):
            seg = seg.split('?')[0]
            if re.fullmatch(r'[A-Za-z]{0,3}[-_]?\d{3,8}', seg):
                found['product_number'] = seg
                sources.append('web address')
                break

    found['_sources'] = sources or ['nothing recognisable']
    return found
