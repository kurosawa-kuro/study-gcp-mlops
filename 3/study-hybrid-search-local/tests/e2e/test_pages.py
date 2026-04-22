"""Playwright smoke tests — Phase 3 の Jinja2 ページ (`/`, `/metrics`, `/data`).

`/search` や `/feedback` は Meilisearch / Redis / PostgreSQL 依存なので本 smoke の対象外。
バックエンド込みで通すなら `make up` でサービスを上げてから別途検証する。
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


class TestIndexPage:
    def test_renders_search_and_feedback_forms(self, page: Page) -> None:
        page.goto("/")
        expect(page).to_have_title(re.compile(r"Predict"))
        expect(page.locator("h1")).to_have_text("Phase2 API Console")
        # search-form / feedback-form の存在確認
        expect(page.locator("form#search-form")).to_be_visible()
        expect(page.locator("form#feedback-form")).to_be_visible()
        # 主要な input
        expect(page.locator("form#search-form input[name='q']")).to_have_value("渋谷 1LDK")
        expect(page.locator("form#feedback-form select[name='action']")).to_be_visible()

    def test_nav_links_present(self, page: Page) -> None:
        page.goto("/")
        # base.html が a[href='/'], a[href='/metrics'], a[href='/data'] を生成
        expect(page.locator("a[href='/']").first).to_be_visible()
        expect(page.locator("a[href='/metrics']").first).to_be_visible()
        expect(page.locator("a[href='/data']").first).to_be_visible()


class TestMetricsPage:
    def test_renders(self, page: Page) -> None:
        page.goto("/metrics")
        expect(page).to_have_title(re.compile(r"Metrics"))
        expect(page.locator("h1")).to_have_text("Runtime Metrics")


class TestDataPage:
    def test_renders_endpoint_catalog(self, page: Page) -> None:
        page.goto("/data")
        expect(page).to_have_title(re.compile(r"Data"))
        expect(page.locator("h1")).to_have_text("Endpoint Catalog")
        # main.py で GET /search と POST /feedback を 2 行流し込んでいる
        expect(page.get_by_text("GET /search")).to_be_visible()
        expect(page.get_by_text("POST /feedback")).to_be_visible()
