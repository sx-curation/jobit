"""
Smoke tests for UX-C gap filter implementation.
Verifies that the required HTML/JS elements and logic exist in index.html.
"""
import re
from pathlib import Path

HTML = (Path(__file__).resolve().parent.parent.parent / 'dashboard' / 'index.html').read_text(encoding='utf-8')


def test_gap_filter_badge_element_exists():
    assert 'id="gap-filter-badge"' in HTML


def test_gap_filter_label_element_exists():
    assert 'id="gap-filter-label"' in HTML


def test_filter_by_missing_skill_function_defined():
    assert 'function filterByMissingSkill(' in HTML


def test_clear_gap_filter_function_defined():
    assert 'function clearGapFilter(' in HTML


def test_gap_skill_filter_variable_declared():
    assert '_gapSkillFilter' in HTML


def test_apply_filters_checks_gap_filter():
    # applyFilters uses normalized key comparison (normalizeSkillKey), not raw string
    assert '_gapSkillFilter' in HTML
    assert 'normalizeSkillKey' in HTML
    # Verify the normalized-key comparison pattern is present
    assert 'key === _gapSkillFilter' in HTML


def test_search_status_auto_attach_on_load():
    # On page load, if a search is running, log panel should auto-open
    assert 'search-status' in HTML
    assert 'd.running' in HTML


def test_render_gap_cards_has_onclick():
    # The gap card onclick must call filterByMissingSkill
    assert "onclick=\"filterByMissingSkill(" in HTML


def test_render_gap_cards_cursor_pointer():
    # Cards should have pointer cursor, not default
    # Find the section in renderGapCards
    match = re.search(r'renderGapCards.*?cursor:(pointer|default)', HTML, re.DOTALL)
    assert match and match.group(1) == 'pointer'


def test_mini_gap_bar_has_onclick():
    # miss-tag spans in updateSkillGap must also be clickable
    assert "miss-tag" in HTML
    # The miss-tag must have onclick in the same line as its definition
    miss_tag_line = [l for l in HTML.splitlines() if 'miss-tag' in l and 'onclick' in l]
    assert len(miss_tag_line) > 0


def test_clear_gap_filter_button_exists():
    assert 'clearGapFilter()' in HTML
    # Badge has a Clear button
    badge_section = HTML[HTML.index('gap-filter-badge'):HTML.index('gap-filter-badge') + 400]
    assert 'clearGapFilter' in badge_section
