from contextlib import suppress
import json
import logging
import subprocess
import sys
from typing import Any, Callable
from urllib.parse import parse_qs, quote, urlencode, urlparse, urlunparse

from sirius_toolbox.collectors.browser.base import BrowserCollector
from sirius_toolbox.collectors.browser.xiaohongshu.parser import parse_note
from sirius_toolbox.collectors.browser.xiaohongshu import selectors
from sirius_toolbox.core.exceptions import CollectorError, LoginRequiredError, UserCancelledError


class XiaohongshuCollector(BrowserCollector):
    def __init__(
        self,
        *,
        headless: bool = True,
        timeout_ms: int = 20000,
        debug: bool = False,
        auto_install_chromium: bool = True,
        progress_callback: Callable[[int, str], None] | None = None,
    ) -> None:
        self._headless = headless
        self._timeout_ms = timeout_ms
        self._debug_enabled = debug
        self._auto_install_chromium = auto_install_chromium
        self._logger = logging.getLogger("sirius_toolbox")
        self._progress_callback = progress_callback

    def _report_step(self, progress: int, message: str) -> None:
        if self._progress_callback is None:
            return
        with suppress(Exception):
            self._progress_callback(max(0, min(100, int(progress))), message)

    def _debug(self, message: str, **fields: Any) -> None:
        if not self._debug_enabled:
            return
        if fields:
            self._logger.info("xhs_debug %s %s", message, json.dumps(fields, ensure_ascii=False))
        else:
            self._logger.info("xhs_debug %s", message)

    @staticmethod
    def _source_id_from_url(url: str) -> str:
        base = url.split("?", 1)[0]
        return base.rstrip("/").split("/")[-1]

    @staticmethod
    def _to_abs_url(base_url: str, href: str) -> str:
        if href.startswith("http://") or href.startswith("https://"):
            return href
        parsed = urlparse(base_url)
        root = f"{parsed.scheme}://{parsed.netloc}"
        if href.startswith("/"):
            return root + href
        return root + "/" + href

    @staticmethod
    def _to_detail_url(url: str) -> str:
        parsed = urlparse(url)
        path = parsed.path or ""
        if "/search_result/" not in path:
            return url

        source_id = path.rstrip("/").split("/")[-1]
        query = parse_qs(parsed.query)
        if query.get("xsec_token") and not (query.get("xsec_source") or [""])[0]:
            query["xsec_source"] = ["pc_search"]

        flat_query = urlencode({k: v[-1] if isinstance(v, list) and v else "" for k, v in query.items()})
        detail_path = f"/explore/{source_id}"
        return urlunparse((parsed.scheme, parsed.netloc, detail_path, "", flat_query, ""))

    @staticmethod
    def _extract_note_payload(page: Any, url: str) -> dict[str, Any]:
        payload = page.evaluate(
            """
            ({ titleSel, contentSel, authorSel, tagSel, imageSel }) => {
                const pickText = (selector) => {
                    const node = document.querySelector(selector);
                    return node ? (node.textContent || '').trim() : '';
                };

                const title = pickText(titleSel)
                    || document.querySelector('meta[property="og:title"]')?.content
                    || '';
                const text = pickText(contentSel)
                    || document.querySelector('meta[name="description"]')?.content
                    || '';
                const author = pickText(authorSel);
                const publishTime = document.querySelector('meta[property="article:published_time"]')?.content || '';
                const noteType = document.querySelector('meta[property="og:type"]')?.content || '';

                const pickAuthorProfile = () => {
                    const node = document.querySelector('.author-container a[href], a[href*="/user/profile/"]');
                    if (!node) return '';
                    const href = node.getAttribute('href') || '';
                    if (!href) return '';
                    return href.startsWith('http') ? href : new URL(href, location.origin).toString();
                };

                const authorProfileUrl = pickAuthorProfile();
                const authorIdMatch = authorProfileUrl.match(/\\/user\\/profile\\/([^/?#]+)/i);
                const authorId = authorIdMatch ? (authorIdMatch[1] || '') : '';

                const parseCount = (raw) => {
                    const textValue = String(raw || '').replace(/[,，\\s]/g, '').trim();
                    if (!textValue) return 0;
                    const num = textValue.match(/\\d+(?:\\.\\d+)?/);
                    if (!num) return 0;
                    const base = Number(num[0]);
                    if (!Number.isFinite(base)) return 0;
                    if (textValue.includes('万')) return Math.round(base * 10000);
                    if (textValue.includes('千')) return Math.round(base * 1000);
                    return Math.round(base);
                };

                const collectActionText = () => {
                    const candidates = [
                        '.interactions .collect-wrapper',
                        '.interactions [class*="collect"]',
                        '.note-action-bar [class*="collect"]',
                        '[class*="collect"]',
                    ];
                    for (const selector of candidates) {
                        const node = document.querySelector(selector);
                        if (node && (node.textContent || '').trim()) return (node.textContent || '').trim();
                    }
                    return '';
                };

                const statTexts = Array.from(document.querySelectorAll('button, [role="button"], .interactions *'))
                    .map((el) => (el.textContent || '').trim())
                    .filter(Boolean);

                const likeRaw = statTexts.find((t) => /赞|like/i.test(t) && /\\d/.test(t)) || '';
                const commentRaw = statTexts.find((t) => /评论|comment/i.test(t) && /\\d/.test(t)) || '';
                const shareRaw = statTexts.find((t) => /分享|share/i.test(t) && /\\d/.test(t)) || '';
                const collectRaw = collectActionText();

                const ipLocation = (() => {
                    const textPool = Array.from(document.querySelectorAll('span,div,p'))
                        .map((el) => (el.textContent || '').trim())
                        .filter(Boolean)
                        .slice(0, 400);
                    const hit = textPool.find((t) => /IP属地/.test(t));
                    return hit || '';
                })();

                const tags = Array.from(document.querySelectorAll(tagSel))
                    .map((el) => (el.textContent || '').trim())
                    .filter(Boolean)
                    .slice(0, 20);

                const pickSrc = (img) => {
                    if (!img) return '';
                    const srcset = img.getAttribute('srcset') || '';
                    if (srcset.trim()) {
                        const first = srcset.split(',')[0]?.trim() || '';
                        const firstUrl = first.split(' ')[0] || '';
                        if (firstUrl) return firstUrl;
                    }
                    return (
                        img.currentSrc
                        || img.getAttribute('src')
                        || img.getAttribute('data-src')
                        || img.getAttribute('data-original')
                        || img.getAttribute('data-xhs-img')
                        || ''
                    );
                };

                const extractBgUrl = (styleValue) => {
                    if (!styleValue) return '';
                    const low = styleValue.toLowerCase();
                    const marker = 'url(';
                    const start = low.indexOf(marker);
                    if (start < 0) return '';
                    const end = styleValue.lastIndexOf(')');
                    if (end <= start + marker.length) return '';
                    let raw = styleValue.slice(start + marker.length, end).trim();
                    if ((raw.startsWith('"') && raw.endsWith('"')) || (raw.startsWith("'") && raw.endsWith("'"))) {
                        raw = raw.slice(1, -1).trim();
                    }
                    return raw;
                };

                const imageCandidates = [];
                for (const img of Array.from(document.querySelectorAll(imageSel))) {
                    imageCandidates.push({
                        src: pickSrc(img),
                        className: String(img.className || '').toLowerCase(),
                        alt: String(img.getAttribute('alt') || '').toLowerCase(),
                        width: Number(img.naturalWidth || img.width || 0),
                        height: Number(img.naturalHeight || img.height || 0),
                    });
                }

                const bgNodes = Array.from(
                    document.querySelectorAll(
                        `${contentSel} [style*='background-image'], .note-content [style*='background-image'], [class*='swiper'] [style*='background-image']`
                    )
                );
                for (const node of bgNodes) {
                    imageCandidates.push({
                        src: extractBgUrl(node.style?.backgroundImage || ''),
                        className: String(node.className || '').toLowerCase(),
                        alt: '',
                        width: 0,
                        height: 0,
                    });
                    imageCandidates.push({
                        src: extractBgUrl(node.getAttribute('style') || ''),
                        className: String(node.className || '').toLowerCase(),
                        alt: '',
                        width: 0,
                        height: 0,
                    });
                }

                const images = imageCandidates
                    .map((item) => ({
                        src: String(item?.src || '').trim(),
                        className: String(item?.className || '').trim(),
                        alt: String(item?.alt || '').trim(),
                        width: Number(item?.width || 0),
                        height: Number(item?.height || 0),
                    }))
                    .filter((item) => !!item.src)
                    .filter((item) => {
                        const src = item.src;
                        const low = src.toLowerCase();
                        if (low.startsWith('data:')) return false;
                        if (low.includes('avatar') || low.includes('headimg') || low.includes('profile')) return false;
                        const classOrAlt = `${item.className} ${item.alt}`;
                        const emojiHints = [
                            'emoji',
                            'emoticon',
                            'sticker',
                            'expression',
                            'face-icon',
                            'emotion',
                        ];
                        if (emojiHints.some((k) => classOrAlt.includes(k) || low.includes(k))) return false;
                        const tinyBySize = item.width > 0 && item.height > 0 && item.width <= 96 && item.height <= 96;
                        if (tinyBySize) return false;
                        return low.startsWith('http://') || low.startsWith('https://');
                    })
                    .map((item) => item.src)
                    .filter((src, idx, arr) => arr.indexOf(src) === idx)
                    .slice(0, 30);

                return {
                    title,
                    text,
                    author,
                    publish_time: publishTime,
                    note_type: noteType,
                    author_profile_url: authorProfileUrl,
                    author_id: authorId,
                    tags,
                    images,
                    like_count_text: likeRaw,
                    like_count: parseCount(likeRaw),
                    collect_count_text: collectRaw,
                    collect_count: parseCount(collectRaw),
                    comment_count_text: commentRaw,
                    comment_count: parseCount(commentRaw),
                    share_count_text: shareRaw,
                    share_count: parseCount(shareRaw),
                    ip_location: ipLocation,
                };
            }
            """,
            {
                "titleSel": selectors.NOTE_TITLE,
                "contentSel": selectors.NOTE_CONTENT,
                "authorSel": selectors.NOTE_AUTHOR,
                "tagSel": selectors.NOTE_TAG,
                "imageSel": selectors.NOTE_IMAGE,
            },
        )
        payload["url"] = url
        payload["source_id"] = XiaohongshuCollector._source_id_from_url(url)
        return payload

    def _collect_note_links(self, page: Any, max_items: int) -> list[str]:
        links: dict[str, str] = {}

        def _link_key(url: str) -> str:
            base = url.split("?", 1)[0]
            return base.rstrip("/")

        def _is_preferred(url: str) -> bool:
            parsed = urlparse(url)
            query = parse_qs(parsed.query)
            has_xsec = bool(query.get("xsec_token"))
            source = (query.get("xsec_source") or [""])[0]
            return has_xsec and source == "pc_search"

        with suppress(Exception):
            page.wait_for_selector(
                f"{selectors.RESULT_CARD_LINK}, {selectors.RESULT_CARD_LINK_FALLBACK}",
                timeout=8000,
            )

        for _ in range(20):
            hrefs = page.evaluate(
                """
                () => {
                    const all = Array.from(document.querySelectorAll('a[href]'));
                    return all
                        .map((el) => el.getAttribute('href') || '')
                        .filter(Boolean)
                        .map((href) => href.startsWith('http') ? href : new URL(href, location.origin).toString());
                }
                """
            )
            for href in hrefs:
                canonical = href.split("?", 1)[0]
                if (
                    "/explore/" in canonical
                    or "/discovery/item/" in canonical
                    or "/note/" in canonical
                ):
                    key = _link_key(href)
                    current = links.get(key)
                    if current is None or (not _is_preferred(current) and _is_preferred(href)):
                        links[key] = href
                if len(links) >= max_items:
                    break
            if len(links) >= max_items:
                break

            page.mouse.wheel(0, 2600)
            page.wait_for_timeout(1200)

        selected = list(links.values())[:max_items]
        self._debug(
            "link_collection_finished",
            discovered=len(links),
            selected=len(selected),
            sample=selected[:3],
        )
        return selected

    def _collect_notes_by_click(self, page: Any, context: Any, max_items: int) -> list[dict[str, Any]]:
        card_selector = f"{selectors.RESULT_CARD_LINK}, {selectors.RESULT_CARD_LINK_FALLBACK}"
        seen_ids: set[str] = set()
        attempted_note_ids: set[str] = set()
        attempted_urls: set[str] = set()
        attempt_counts: dict[str, int] = {}
        collected: list[dict[str, Any]] = []

        def _smooth_scroll(round_idx: int) -> None:
            # Smaller wheel chunks feel more like natural browsing and less like page refresh jumps.
            chunks = [240, 240, 240] if round_idx < 8 else [280, 280, 280]
            for delta in chunks:
                page.mouse.wheel(0, delta)
                page.wait_for_timeout(180)
            page.wait_for_timeout(380)

        def _dismiss_note_overlay(mode: str = "") -> bool:
            # Prefer dismissing in-page detail without triggering a history navigation.
            with suppress(Exception):
                page.keyboard.press("Escape")
                page.wait_for_timeout(300)

            if mode == "overlay":
                with suppress(Exception):
                    point = page.evaluate(
                        """
                        ({ titleSel, contentSel }) => {
                            const viewportW = window.innerWidth || document.documentElement.clientWidth || 0;
                            const viewportH = window.innerHeight || document.documentElement.clientHeight || 0;
                            const node = document.querySelector(contentSel) || document.querySelector(titleSel);
                            if (!node || !viewportW || !viewportH) {
                                return { ok: false, x: 0, y: 0 };
                            }
                            const card = node.closest('[class*="note"], [class*="content"], [class*="dialog"], article, section, div') || node;
                            const rect = card.getBoundingClientRect();
                            let x = Math.min(viewportW - 10, rect.right + 24);
                            if (x <= rect.right + 2) {
                                x = Math.max(10, rect.left - 24);
                            }
                            const y = Math.max(10, Math.min(viewportH - 10, rect.top + Math.min(48, Math.max(16, rect.height / 6))));
                            const ok = x > 0 && y > 0 && x < viewportW && y < viewportH;
                            return { ok, x, y };
                        }
                        """,
                        {"titleSel": selectors.NOTE_TITLE, "contentSel": selectors.NOTE_CONTENT},
                    )
                    if bool(point.get("ok")):
                        page.mouse.click(float(point["x"]), float(point["y"]))
                        page.wait_for_timeout(300)

            with suppress(Exception):
                page.click(
                    "button[aria-label*='关闭'], button[title*='关闭'], "
                    "[class*='close'] button, [class*='close-icon'], [class*='icon-close']",
                    timeout=600,
                )
                page.wait_for_timeout(350)

            try:
                still_visible = page.evaluate(
                    """
                    ({ titleSel, contentSel }) => {
                        const node = document.querySelector(contentSel) || document.querySelector(titleSel);
                        if (!node) return false;
                        const style = window.getComputedStyle(node);
                        if (style.display === 'none' || style.visibility === 'hidden') return false;
                        const rect = node.getBoundingClientRect();
                        return rect.width > 5 && rect.height > 5;
                    }
                    """,
                    {"titleSel": selectors.NOTE_TITLE, "contentSel": selectors.NOTE_CONTENT},
                )
                return not bool(still_visible)
            except Exception:
                return False

        def _visible_candidates() -> list[dict[str, Any]]:
            return page.evaluate(
                """
                ({ selector }) => {
                    const isVisible = (el) => {
                        if (!el) return false;
                        const style = window.getComputedStyle(el);
                        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
                            return false;
                        }
                        const rect = el.getBoundingClientRect();
                        return rect.width > 4 && rect.height > 4;
                    };

                    const anchors = Array.from(document.querySelectorAll(selector));
                    const result = [];
                    const seen = new Set();
                    for (const a of anchors) {
                        const href = a.getAttribute('href') || '';
                        if (!href) continue;
                        const abs = href.startsWith('http') ? href : new URL(href, location.origin).toString();
                        if (
                            !(abs.includes('/explore/') || abs.includes('/discovery/item/') || abs.includes('/note/'))
                        ) {
                            continue;
                        }
                        const card = a.closest('[class*="note"], [class*="card"], section, article, div') || a;
                        const target = isVisible(card) ? card : a;
                        if (!isVisible(target)) continue;
                        if (!seen.has(abs)) {
                            seen.add(abs);
                            const rect = target.getBoundingClientRect();
                            const viewportH = window.innerHeight || document.documentElement.clientHeight || 0;
                            const inViewport = rect.bottom > 80 && rect.top < (viewportH - 20);
                            if (!inViewport) continue;

                            const rawX = rect.left + rect.width / 2;
                            const rawY = rect.top + Math.min(120, rect.height / 2);
                            const x = Math.max(8, Math.min(window.innerWidth - 8, rawX));
                            const y = Math.max(8, Math.min(viewportH - 8, rawY));
                            result.push({
                                href: abs,
                                x,
                                y,
                            });
                        }
                    }
                    result.sort((a, b) => (a.y - b.y) || (a.x - b.x));
                    return result;
                }
                """,
                {"selector": card_selector},
            )

        with suppress(Exception):
            page.wait_for_selector(card_selector, timeout=8000)

        stop_click_flow = False
        for round_idx in range(40):
            if stop_click_flow:
                break
            if len(collected) >= max_items:
                break

            collected_before = len(collected)
            candidates = _visible_candidates()
            self._debug("click_scan_round", card_count=len(candidates), collected=len(collected))
            self._report_step(
                40 + min(45, int((len(collected) / max(1, max_items)) * 45)),
                f"扫描帖子卡片：第{round_idx + 1}轮，可见{len(candidates)}条，已采集{len(collected)}条",
            )

            attempted_in_round = 0
            for idx, candidate in enumerate(candidates):
                if len(collected) >= max_items:
                    break
                candidate_url = str(candidate.get("href") or "")
                click_x = float(candidate.get("x") or 0)
                click_y = float(candidate.get("y") or 0)
                if not candidate_url or click_x <= 0 or click_y <= 0:
                    continue
                if candidate_url in attempted_urls:
                    continue
                note_id = self._source_id_from_url(candidate_url)
                if not note_id:
                    continue
                if note_id in attempted_note_ids:
                    continue
                if attempt_counts.get(note_id, 0) >= 2:
                    attempted_note_ids.add(note_id)
                    attempted_urls.add(candidate_url)
                    continue
                if note_id in seen_ids:
                    continue

                attempt_counts[note_id] = attempt_counts.get(note_id, 0) + 1
                attempted_in_round += 1
                note_page = None
                opened_new_tab = False
                interaction_mode = ""
                before_url = page.url
                self._report_step(
                    45 + min(40, int((len(collected) / max(1, max_items)) * 40)),
                    f"尝试打开帖子：{note_id}",
                )
                try:
                    try:
                        # Keep current list page stable by preferring opening detail in a new tab.
                        with context.expect_page(timeout=2500) as page_info:
                            page.mouse.click(click_x, click_y, button="middle")
                        note_page = page_info.value
                        opened_new_tab = True
                        interaction_mode = "new_tab"
                        note_page.wait_for_load_state("domcontentloaded", timeout=self._timeout_ms)
                    except Exception:
                        try:
                            with context.expect_page(timeout=2500) as page_info:
                                page.keyboard.down("Control")
                                page.mouse.click(click_x, click_y)
                                page.keyboard.up("Control")
                            note_page = page_info.value
                            opened_new_tab = True
                            interaction_mode = "new_tab"
                            note_page.wait_for_load_state("domcontentloaded", timeout=self._timeout_ms)
                        except Exception:
                            with suppress(Exception):
                                page.keyboard.up("Control")

                        # Some cards navigate in the same tab instead of opening a new one.
                            page.mouse.click(click_x, click_y)
                            page.wait_for_timeout(1200)
                            now_url = page.url
                            if now_url != before_url and (
                                "/explore/" in now_url or "/discovery/item/" in now_url or "/note/" in now_url
                            ):
                                note_page = page
                                interaction_mode = "same_tab_nav"
                            else:
                                # A common XHS flow opens detail as in-page overlay without URL change.
                                try:
                                    page.wait_for_selector(
                                        f"{selectors.NOTE_CONTENT}, {selectors.NOTE_TITLE}",
                                        timeout=1000,
                                    )
                                    note_page = page
                                    interaction_mode = "overlay"
                                except Exception:
                                    continue

                    if note_page is None:
                        continue

                    note_url = note_page.url or candidate_url
                    if opened_new_tab:
                        detail_url = self._to_detail_url(note_url)
                        if detail_url != note_url:
                            try:
                                note_page.goto(detail_url, wait_until="domcontentloaded", timeout=self._timeout_ms)
                                note_page.wait_for_timeout(900)
                                note_url = note_page.url or detail_url
                            except Exception:
                                note_url = note_page.url or note_url
                    attempted_note_ids.add(note_id)
                    attempted_urls.add(candidate_url)
                    payload = self._extract_note_payload(note_page, note_url)
                    parsed = parse_note(payload)
                    collected.append(parsed)
                    seen_ids.add(parsed.get("source_id") or note_id)
                    self._debug(
                        "note_collected_by_click",
                        index=idx,
                        opened_new_tab=opened_new_tab,
                        click_x=round(click_x, 2),
                        click_y=round(click_y, 2),
                        url=note_url,
                        title=parsed.get("title", ""),
                        image_count=len(parsed.get("images", [])),
                    )
                    # Refresh candidates after each successful click/back cycle to avoid stale coordinates.
                    break
                except Exception as exc:  # noqa: BLE001
                    self._debug("note_click_failed", index=idx, error=str(exc))
                    if attempt_counts.get(note_id, 0) >= 2:
                        attempted_note_ids.add(note_id)
                        attempted_urls.add(candidate_url)
                    continue
                finally:
                    if opened_new_tab and note_page is not None and not note_page.is_closed():
                        with suppress(Exception):
                            note_page.close()
                    elif not opened_new_tab and note_page is page:
                        dismissed = _dismiss_note_overlay(interaction_mode)
                        if not dismissed and interaction_mode == "same_tab_nav":
                            # Do not use browser back to avoid list refresh/reorder side effects.
                            self._debug("same_tab_nav_not_dismissed_stop_flow", url=page.url)
                            self._report_step(88, "检测到同页导航且无法安全关闭，停止点击流以避免页面刷新")
                            stop_click_flow = True
                            break

            if attempted_in_round == 0:
                self._debug("click_round_no_fresh_candidates", attempted_total=len(attempted_urls))
                self._report_step(80, "本轮没有可点击的新卡片，执行下滑加载")

            if len(collected) > collected_before:
                # Keep viewport stable after a successful collection before next scan.
                page.wait_for_timeout(350)
                continue

            _smooth_scroll(round_idx)

        self._debug("click_collection_finished", total=len(collected))
        return collected

    def _collect_notes_by_open_links(self, context: Any, links: list[str], max_items: int) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for link in links[:max_items]:
            note_page = context.new_page()
            try:
                note_page.goto(link, wait_until="domcontentloaded", timeout=self._timeout_ms)
                note_page.wait_for_timeout(1000)
                payload = self._extract_note_payload(note_page, link)
                parsed = parse_note(payload)
                results.append(parsed)
                self._debug(
                    "note_collected_by_fallback_open",
                    url=link,
                    title=parsed.get("title", ""),
                    image_count=len(parsed.get("images", [])),
                )
            finally:
                with suppress(Exception):
                    note_page.close()
        return results

    @staticmethod
    def _login_probe(page: Any) -> dict[str, Any]:
        return page.evaluate(
            """
            () => {
                const text = (document.body?.innerText || '').slice(0, 15000);
                const loginHints = ['登录后', '登录查看', '请先登录', '手机号登录', '微信登录', '扫码登录'];
                const matchedHints = loginHints.filter((hint) => text.includes(hint));

                const loginNodes = [
                    '[class*="login-panel"]',
                    '[class*="login-mask"]',
                    '.login-panel',
                    '.login-mask',
                    '.mask',
                ];
                const nodeMatches = loginNodes.filter((s) => !!document.querySelector(s));

                const ctaCount = Array.from(document.querySelectorAll('button,a,div,span'))
                    .filter((el) => {
                        const t = (el.textContent || '').trim();
                        if (!t) return false;
                        if (!(t.includes('登录') || t.includes('扫码'))) return false;
                        const rect = el.getBoundingClientRect();
                        return rect.width > 0 && rect.height > 0;
                    })
                    .length;

                const isRequired = matchedHints.length > 0 && (nodeMatches.length > 0 || ctaCount >= 2);
                const riskByUrl = location.href.includes('/website-login/error') || location.search.includes('error_code=');
                const riskHints = ['安全限制', 'IP存在风险', '网络环境', '稍后再试'];
                const matchedRiskHints = riskHints.filter((hint) => text.includes(hint));
                const riskBlocked = riskByUrl || matchedRiskHints.length > 0;

                return {
                    is_required: isRequired,
                    risk_blocked: riskBlocked,
                    matched_hints: matchedHints,
                    matched_risk_hints: matchedRiskHints,
                    matched_selectors: nodeMatches,
                    visible_login_cta_count: ctaCount,
                    url: location.href,
                    title: document.title || '',
                };
            }
            """
        )

    @staticmethod
    def _is_login_required(page: Any) -> bool:
        probe = XiaohongshuCollector._login_probe(page)
        return bool(probe.get("is_required"))

    def _wait_for_login(self, page: Any, timeout_sec: int = 300) -> None:
        waited = 0
        while self._is_login_required(page):
            probe = self._login_probe(page)
            self._debug("login_waiting", waited_sec=waited, probe=probe)
            if bool(probe.get("risk_blocked")):
                raise CollectorError(
                    "Xiaohongshu returned security restriction page (IP/network risk). "
                    "Switch to a trusted network and retry."
                )
            if page.is_closed():
                raise UserCancelledError("Browser closed by user, social collection terminated")

            page.wait_for_timeout(1000)
            waited += 1
            if waited >= timeout_sec:
                raise LoginRequiredError(
                    "Login is required but was not completed in time. "
                    "Please login in the opened browser and retry."
                )

    @staticmethod
    def _is_missing_chromium_error(exc: Exception) -> bool:
        msg = str(exc).lower()
        hints = [
            "executable doesn't exist",
            "browser type chromium",
            "playwright install",
            "failed to launch",
        ]
        return any(h in msg for h in hints)

    def _install_chromium_runtime(self) -> bool:
        commands = [
            [sys.executable, "-m", "playwright", "install", "chromium"],
            ["playwright", "install", "chromium"],
        ]
        for cmd in commands:
            try:
                self._debug("install_chromium_try", command=" ".join(cmd))
                subprocess.run(cmd, check=True)
                self._debug("install_chromium_ok", command=" ".join(cmd))
                return True
            except Exception as install_exc:  # noqa: BLE001
                self._debug("install_chromium_failed", command=" ".join(cmd), error=str(install_exc))
        return False

    def collect(self, keyword: str, max_items: int) -> list[dict[str, Any]]:
        keyword = keyword.strip()
        if max_items <= 0:
            return []

        self._report_step(10, f"启动小红书采集，关键词：{keyword}")

        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "Playwright is required for Xiaohongshu collection. "
                "Install dependency and run: playwright install chromium"
            ) from exc

        search_url = (
            f"{selectors.SEARCH_PAGE_URL}?keyword={quote(keyword)}&source=web_explore_feed"
        )
        results: list[dict[str, Any]] = []
        self._debug(
            "collect_started",
            keyword=keyword,
            max_items=max_items,
            headless=self._headless,
            search_url=search_url,
        )

        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=self._headless)
            except Exception as exc:  # noqa: BLE001
                if self._auto_install_chromium and self._is_missing_chromium_error(exc):
                    self._report_step(15, "检测到 Chromium 运行时缺失，正在自动安装")
                    if self._install_chromium_runtime():
                        self._report_step(18, "Chromium 安装完成，继续启动浏览器")
                        browser = playwright.chromium.launch(headless=self._headless)
                    else:
                        raise RuntimeError(
                            "Chromium runtime is missing and auto-install failed. "
                            "Please run: python -m playwright install chromium"
                        ) from exc
                else:
                    raise
            context = browser.new_context(locale="zh-CN")

            try:
                page = context.new_page()
                page.goto(
                    selectors.EXPLORE_HOME_URL,
                    wait_until="domcontentloaded",
                    timeout=self._timeout_ms,
                )
                self._debug("goto_home", url=page.url)
                page.goto(search_url, wait_until="domcontentloaded", timeout=self._timeout_ms)
                page.wait_for_timeout(1800)
                self._report_step(20, "已进入搜索结果页，检查登录状态")
                login_probe = self._login_probe(page)
                self._debug("after_search_open", probe=login_probe)

                if bool(login_probe.get("risk_blocked")):
                    raise CollectorError(
                        "Xiaohongshu returned security restriction page (IP/network risk). "
                        "Switch to a trusted network and retry."
                    )

                if bool(login_probe.get("is_required")):
                    if self._headless:
                        raise LoginRequiredError(
                            "Xiaohongshu requires login for this query. "
                            "Use headed mode and complete login in browser window."
                        )
                    self._report_step(25, "需要登录，请在浏览器完成登录")
                    self._wait_for_login(page)
                    page.goto(search_url, wait_until="domcontentloaded", timeout=self._timeout_ms)
                    page.wait_for_timeout(1500)
                    self._debug("after_login_refresh", probe=self._login_probe(page))
                    self._report_step(30, "登录已完成，重新进入搜索结果")

                results = self._collect_notes_by_click(page, context, max_items=max_items)
                if not results:
                    self._debug("no_notes_collected_by_click", probe=self._login_probe(page), current_url=page.url)
                    self._report_step(86, "点击流未拿到结果，切换链接兜底模式")
                    links = self._collect_note_links(page, max_items=max_items)
                    if links:
                        self._debug("fallback_to_open_links", link_count=len(links))
                        results = self._collect_notes_by_open_links(context, links, max_items=max_items)

                if not results:
                    raise CollectorError(
                        "No notes collected after click-first and fallback-open flows. "
                        "Please confirm cards are visible and retry with a broader keyword."
                    )
                self._debug("collect_finished", total=len(results))
                self._report_step(95, f"采集完成，获得{len(results)}条帖子")
            except Exception as exc:  # noqa: BLE001
                if isinstance(exc, (LoginRequiredError, UserCancelledError)):
                    self._debug("collect_interrupted", error=str(exc), error_type=type(exc).__name__)
                    self._report_step(100, f"任务中断：{exc}")
                    raise

                message = str(exc).lower()
                closed_hints = ["has been closed", "target page", "browser has been closed"]
                if any(h in message for h in closed_hints):
                    self._debug("collect_interrupted", error=str(exc), error_type=type(exc).__name__)
                    self._report_step(100, "任务中断：浏览器被关闭")
                    raise UserCancelledError("Browser closed by user, social collection terminated") from exc
                self._debug("collect_failed", error=str(exc), error_type=type(exc).__name__)
                self._report_step(100, f"任务失败：{exc}")
                raise
            finally:
                with suppress(Exception):
                    context.close()
                with suppress(Exception):
                    browser.close()

        self._report_step(100, "任务结束")
        return results
