"""Checks on the browser-side code.

Scoped by what actually broke while building this. Of the JavaScript faults
introduced, two were pure syntax or API-shape errors -- a jQuery method called
on a native Promise, and a quoted string spanning two lines -- which no Python
test could ever see but `node --check` catches instantly. One was a logic error
(a refresh that ignored the active filter) which needs a real browser.

So these cover the cheap, high-yield half: does the script parse, does every
page render, and does the JavaScript still agree with the templates about
element names. Interaction testing would need a browser driver and is a
separate decision.
"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = Path(__file__).parent.parent
TEMPLATES = ROOT / 'templates'
MAIN_JS = ROOT / 'static' / 'js' / 'main.js'

# Ids the scripts create at runtime rather than finding in a template. Keeping
# this list explicit is the point: an id that disappears from a template shows
# up here as a decision rather than a silent breakage.
RUNTIME_IDS = set()


def node():
    return shutil.which('node')


class TestScriptsParse:
    """Catches the class of error that reached the browser twice here."""

    @pytest.mark.skipif(not shutil.which('node'), reason='node not installed')
    def test_main_js_parses(self):
        result = subprocess.run([node(), '--check', str(MAIN_JS)],
                                capture_output=True, text=True)
        assert result.returncode == 0, result.stderr

    @pytest.mark.skipif(not shutil.which('node'), reason='node not installed')
    @pytest.mark.parametrize('template', sorted(
        p.name for p in TEMPLATES.glob('*.html')))
    def test_inline_scripts_parse(self, template, tmp_path):
        """Most of the UI lives in <script> blocks inside templates."""
        html = (TEMPLATES / template).read_text(encoding='utf-8')
        blocks = re.findall(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>',
                            html, re.S | re.I)
        for i, block in enumerate(blocks):
            # Jinja expressions are not JavaScript; replace them with a literal
            # so the parser sees the shape of the code rather than the braces.
            code = re.sub(r'\{\{.*?\}\}', 'null', block, flags=re.S)
            code = re.sub(r'\{%.*?%\}', '', code, flags=re.S)
            path = tmp_path / f'{template}.{i}.js'
            path.write_text(code, encoding='utf-8')
            result = subprocess.run([node(), '--check', str(path)],
                                    capture_output=True, text=True)
            assert result.returncode == 0, (
                f'{template} script block {i}:\n{result.stderr}')


class TestScriptsAgreeWithTemplates:
    def test_every_element_id_the_script_reads_exists(self):
        """A renamed id in a template otherwise breaks the script silently."""
        js = MAIN_JS.read_text(encoding='utf-8')
        referenced = (set(re.findall(r"\$\('#([A-Za-z][\w-]*)'", js))
                      | set(re.findall(r"getElementById\('([\w-]+)'", js)))

        present = set()
        for template in TEMPLATES.glob('*.html'):
            present |= set(re.findall(r'id="([A-Za-z][\w-]*)"',
                                      template.read_text(encoding='utf-8')))

        missing = referenced - present - RUNTIME_IDS
        assert not missing, (
            f'main.js reads ids that no template defines: {sorted(missing)}')


class TestPagesRender:
    """A template that fails to render is a 500 nobody sees until they click."""

    @pytest.mark.parametrize('path', [
        '/', '/freezer', '/storage-editor', '/antibodies', '/history',
        '/bookmarklet', '/import-export', '/kiosk',
        '/calculator/dilution', '/calculator/actual-concentration',
    ])
    def test_page_renders(self, client, path):
        response = client.get(path)
        assert response.status_code == 200, f'{path} returned {response.status_code}'
        assert len(response.data) > 500, f'{path} rendered suspiciously little'

    def test_kiosk_is_standalone(self, client):
        """The display must not depend on the desk UI's framework or nav."""
        html = client.get('/kiosk').data.decode('utf-8')
        assert 'bootstrap' not in html.lower()
        assert 'navbar' not in html.lower()

    def test_pages_load_no_external_resources(self, client):
        """Everything must work with no internet: the panel has none to spare
        and the lab network may not route to a CDN."""
        for path in ('/', '/freezer', '/kiosk'):
            html = client.get(path).data.decode('utf-8')
            # Only resources the browser fetches: a script/image src, or a
            # <link> stylesheet or font. An <a href> is navigation -- the
            # footer credit is one, and is fine.
            external = (re.findall(r'\ssrc="(https?://[^"]+)"', html)
                        + re.findall(r'<link[^>]+href="(https?://[^"]+)"', html))
            assert not external, f'{path} loads external resources: {external}'
