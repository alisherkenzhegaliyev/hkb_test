from __future__ import annotations

import logging
from playwright.async_api import async_playwright

from src.config import settings

logger = logging.getLogger(__name__)

EMPLOYER_URL = f"https://almaty.hh.kz/employer/{settings.employer_id}?tab=VACANCIES&area=160&area=40"


async def scrape_vacancies() -> list[dict]:
    """Scrape all open vacancies from hh.kz employer page. Returns list of vacancy dicts."""
    vacancies: list[dict] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="ru-KZ",
        )
        page = await context.new_page()

        logger.info("Navigating to employer page: %s", EMPLOYER_URL)
        await page.goto(EMPLOYER_URL, wait_until="domcontentloaded", timeout=60_000)
        await page.wait_for_timeout(3000)


        vacancy_links: list[str] = []
        while True:
            # Match any <a> whose href contains /vacancy/ — works across all hh.kz page layouts
            links = await page.eval_on_selector_all(
                "a[href*='/vacancy/']",
                "els => [...new Set(els.map(e => e.href))]",
            )
            for link in links:
                base = link.split("?")[0]
                if "/vacancy/" in base and base not in vacancy_links:
                    vacancy_links.append(base)

            logger.info("Collected %d vacancy links so far", len(vacancy_links))

            next_btn = page.locator("a[data-qa='pager-next']")
            if await next_btn.count() == 0:
                break
            await next_btn.click()
            await page.wait_for_timeout(2000)

        logger.info("Total vacancy links found: %d", len(vacancy_links))

        for url in vacancy_links:
            try:
                vac = await _scrape_vacancy_page(context, url)
                if vac:
                    vacancies.append(vac)
            except Exception as exc:
                logger.warning("Failed to scrape vacancy %s: %s", url, exc)

        await browser.close()

    logger.info("Scraped %d vacancies", len(vacancies))
    return vacancies


async def _scrape_vacancy_page(context, url: str) -> dict | None:
    page = await context.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        await page.wait_for_timeout(1000)

        hh_id = _extract_hh_id(url)

        # Title
        title = ""
        for sel in ["[data-qa='vacancy-title']", "h1"]:
            el = page.locator(sel).first
            if await el.count():
                title = (await el.inner_text()).strip()
                break

        # Description
        description = ""
        for sel in ["div[data-qa='vacancy-description']", ".vacancy-description", ".g-user-content"]:
            el = page.locator(sel).first
            if await el.count():
                description = (await el.inner_text()).strip()
                break

        # Key skills
        requirements: list[str] = []
        for sel in ["li[data-qa='skills-element']", ".vacancy-skill-tag", "[data-qa='bloko-tag__text']"]:
            items = page.locator(sel)
            count = await items.count()
            if count:
                for i in range(count):
                    txt = (await items.nth(i).inner_text()).strip()
                    if txt:
                        requirements.append(txt)
                break

        # Card metadata
        async def _text(qa: str) -> str | None:
            el = page.locator(f"[data-qa='{qa}']").first
            return (await el.inner_text()).strip() if await el.count() else None

        meta: dict = {}
        if v := await _text("vacancy-experience"):
            meta["experience"] = v
        if v := await _text("vacancy-salary"):
            meta["salary"] = v

        # Employment type / schedule — hh.kz puts these in <p> tags inside the card
        employment_els = page.locator("p.vacancy-description-list-item")
        emp_count = await employment_els.count()
        extras: list[str] = []
        for i in range(emp_count):
            txt = (await employment_els.nth(i).inner_text()).strip()
            if txt:
                extras.append(txt)
        if extras:
            meta["conditions"] = extras

        if not title:
            logger.warning("No title found for %s — skipping", url)
            return None

        return {
            "hh_id": hh_id,
            "title": title,
            "description": description,
            "requirements": requirements,
            "meta": meta,
            "url": url,
        }
    finally:
        await page.close()


def _extract_hh_id(url: str) -> str:
    parts = url.rstrip("/").split("/")
    for i, part in enumerate(parts):
        if part == "vacancy" and i + 1 < len(parts):
            return parts[i + 1].split("?")[0]
    return url.split("?")[0].split("/")[-1]
