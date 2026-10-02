"""Tests for filling a record from a supplier's product page.

The parsing is heuristic by nature, so these pin the behaviours that matter:
that nothing dangerous is invented, that junk is rejected, and that the
catalogue-number patterns cover how real vendors actually label them.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lookup
from lookup import LookupError_


JSON_LD_PAGE = '''
<html><head>
<script type="application/ld+json">
{"@context":"https://schema.org/","@type":"Product",
 "name":"Human IL-2 Recombinant Protein",
 "sku":"200-02-50UG","brand":"Gibco",
 "description":"Recombinant Human IL-2 is a 15.5 kDa protein with an IC50 of 140 nM."}
</script>
</head><body></body></html>
'''


class TestNothingInvented:
    """The failure that matters: a plausible number that is simply wrong."""

    def test_potency_figures_are_not_taken_as_concentration(self):
        got = lookup.extract('https://example.com/p/1', html=JSON_LD_PAGE)
        # "IC50 of 140 nM" in the description must not become a stock
        # concentration -- someone would dilute from it.
        assert 'stock_concentration' not in got
        assert 'stock_unit' not in got

    def test_labelled_concentration_is_taken(self):
        page = JSON_LD_PAGE.replace('an IC50 of 140 nM',
                                    'a concentration: 10 mg/mL')
        got = lookup.extract('https://example.com/p/1', html=page)
        assert got['stock_concentration'] == 10.0
        assert got['stock_unit'] == 'mg/mL'

    def test_placeholder_values_are_rejected(self):
        page = JSON_LD_PAGE.replace('"brand":"Gibco"', '"brand":"-"')
        got = lookup.extract('https://example.com/p/1', html=page)
        # Falls back to the host rather than storing a literal dash.
        assert got['supplier'] == 'example.com'

    def test_a_title_that_is_only_the_vendor_is_not_a_product_name(self):
        page = '<html><head><title>Miltenyi Biotec</title></head><body></body></html>'
        got = lookup.extract('https://www.miltenyibiotec.com/p/x', html=page)
        assert 'drug_name' not in got


class TestStructuredData:
    def test_reads_schema_org_product(self):
        got = lookup.extract('https://example.com/p/1', html=JSON_LD_PAGE)
        assert got['drug_name'] == 'Human IL-2 Recombinant Protein'
        assert got['product_number'] == '200-02-50UG'
        assert got['supplier'] == 'Gibco'
        assert got['notes'].startswith('Recombinant Human IL-2')

    def test_pack_size_comes_out_of_the_catalogue_number(self):
        got = lookup.extract('https://example.com/p/1', html=JSON_LD_PAGE)
        assert got['aliquot_volume'] == '50 µg'

    def test_double_escaped_characters_are_decoded(self):
        # Some vendors escape their JSON twice, so the decoded string still
        # contains a literal backslash-u rather than the character itself.
        page = JSON_LD_PAGE.replace('Protein"', r'Protein, PeproTech\u00AE"')
        got = lookup.extract('https://example.com/p/1', html=page)
        assert r'\u' not in got['drug_name']
        assert got['drug_name'].endswith('\u00AE')


class TestPastedText:
    """For vendors that refuse this server or render in the browser."""

    PASTED = ('Human VEGF-165 IS, premium grade\n'
              'Order no. 130-109-386\n'
              'Recombinant human VEGF-165 is a disulfide-linked homodimeric '
              'glycoprotein that stimulates endothelial proliferation.\n'
              'Size: 25 ug')

    def test_name_catalogue_and_size_from_plain_text(self):
        got = lookup.extract('https://www.miltenyibiotec.com/p/x', html=self.PASTED)
        assert got['drug_name'] == 'Human VEGF-165 IS, premium grade'
        assert got['product_number'] == '130-109-386'
        assert got['aliquot_volume'] == '25 µg'
        assert 'disulfide-linked' in got['notes']

    @pytest.mark.parametrize('text,expected', [
        ('Cat. No. 4423', '4423'),
        ('Order no. 130-109-386', '130-109-386'),
        ('Product Number F6886', 'F6886'),
        ('Catalog #: HY-10431', 'HY-10431'),
        ('Item No. 10005583', '10005583'),
        ('REF 200-02-50UG', '200-02-50UG'),
        ('Cat no: ab9596', 'ab9596'),
    ])
    def test_catalogue_number_labelling_styles(self, text, expected):
        m = (lookup.CATALOGUE_LABELLED.search(text)
             or lookup.CATALOGUE_SHAPED.search(text))
        assert m and m.group(1) == expected


class TestRefusesPrivateAddresses:
    """The app has no authentication, so an unguarded fetcher would let anyone
    on the network reach internal services through this machine."""

    @pytest.mark.parametrize('url', [
        'http://127.0.0.1/',
        'http://localhost:5000/api/records',
        'http://10.0.0.5/',
        'http://192.168.1.1/',
        'http://169.254.169.254/latest/meta-data/',
    ])
    def test_private_and_loopback_refused(self, url):
        with pytest.raises(LookupError_, match='private network'):
            lookup.fetch(url)

    @pytest.mark.parametrize('url', ['file:///C:/Windows/win.ini',
                                     'ftp://example.com/x', 'not a url'])
    def test_non_http_schemes_refused(self, url):
        with pytest.raises(LookupError_, match='http'):
            lookup.fetch(url)
