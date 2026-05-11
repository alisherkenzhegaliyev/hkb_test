"""Streamlit frontend for AI Recruiting Agent — Home Credit Bank."""

from __future__ import annotations

import os
import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="AI Recruiting Agent — HCB",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def api_get(path: str, params: dict | None = None, timeout: int = 30):
    try:
        r = requests.get(f"{API_URL}{path}", params=params, timeout=timeout)
        r.raise_for_status()
        return r.json(), None
    except requests.exceptions.ConnectionError:
        return None, f"Cannot connect to API at {API_URL}"
    except requests.exceptions.Timeout:
        return None, "Request timed out"
    except requests.exceptions.HTTPError as e:
        detail = ""
        try:
            detail = e.response.json().get("detail", "")
        except Exception:
            pass
        return None, f"HTTP {e.response.status_code}: {detail or str(e)}"
    except Exception as e:
        return None, str(e)


def api_post(path: str, json_data: dict | None = None, files=None, timeout: int | None = None):
    try:
        kwargs: dict = {"timeout": timeout}
        if files:
            kwargs["files"] = files
        elif json_data is not None:
            kwargs["json"] = json_data
        r = requests.post(f"{API_URL}{path}", **kwargs)
        r.raise_for_status()
        return r.json(), None
    except requests.exceptions.ConnectionError:
        return None, f"Cannot connect to API at {API_URL}"
    except requests.exceptions.Timeout:
        return None, "Request timed out"
    except requests.exceptions.HTTPError as e:
        detail = ""
        try:
            detail = e.response.json().get("detail", "")
        except Exception:
            pass
        return None, f"HTTP {e.response.status_code}: {detail or str(e)}"
    except Exception as e:
        return None, str(e)


def score_bar(label: str, value: float) -> None:
    pct = int(value * 100)
    st.markdown(f"**{label}:** {pct}%")
    st.progress(min(max(value, 0.0), 1.0))


# ── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("AI Recruiting Agent")
    st.caption("Home Credit Bank — Internal Tool")
    st.divider()
    st.markdown(f"**Backend:** `{API_URL}`")

    health, _err = api_get("/health", timeout=5)
    if health:
        st.success(
            f"API online — {health.get('candidate_count', 0)} candidates, "
            f"{health.get('vacancy_count', 0)} vacancies"
        )
    else:
        st.error("API offline")

    st.divider()
    st.markdown("**Sync vacancies from hh.kz**")
    if st.button("Sync from hh.kz", use_container_width=True):
        with st.spinner("Scraping hh.kz — this may take 30–60 s..."):
            data, err = api_post("/vacancies/scrape", json_data={}, timeout=300)
        if err:
            st.error(err)
        else:
            st.success(
                f"Scrape complete: {data.get('imported', 0)} new / "
                f"{data.get('total', 0)} total vacancies."
            )


# ── Tabs ─────────────────────────────────────────────────────────────────────

tab_vacancies, tab_upload, tab_match, tab_status = st.tabs(
    ["Vacancies", "Upload Resume", "Match Candidates", "Status"]
)

# ── TAB 1: VACANCIES ─────────────────────────────────────────────────────────
with tab_vacancies:
    st.header("Vacancy List")
    st.caption("Vacancies scraped from hh.kz. Use 'Sync from hh.kz' in the sidebar to refresh.")

    vacancies, err = api_get("/vacancies/")
    if err:
        st.error(err)
    elif not vacancies:
        st.info("No vacancies yet. Use Sync from hh.kz in the sidebar.")
    else:
        for v in vacancies:
            url = v.get("url") or ""
            link = f"[Open on hh.kz]({url})" if url else "—"
            with st.expander(f"#{v.get('id')} — {v.get('title', 'Untitled')}"):
                st.markdown(f"**Link:** {link}")
                st.markdown(f"**Scraped:** {str(v.get('scraped_at', ''))[:19]}")
                meta = v.get("meta") or {}
                if meta:
                    cols = st.columns(3)
                    if exp := meta.get("experience"):
                        cols[0].markdown(f"**Experience:** {exp}")
                    if sal := meta.get("salary"):
                        cols[1].markdown(f"**Salary:** {sal}")
                    if conds := meta.get("conditions"):
                        cols[2].markdown("**Conditions:** " + " · ".join(conds))
                reqs = v.get("requirements") or []
                if reqs:
                    st.markdown("**Key skills:** " + " · ".join(f"`{r}`" for r in reqs))
                desc = v.get("description", "")
                if desc:
                    st.markdown("**Description:**")
                    st.write(desc)
        st.caption(f"Total: {len(vacancies)} vacancies")

# ── TAB 2: UPLOAD RESUME ─────────────────────────────────────────────────────
with tab_upload:
    st.header("Upload Resume")
    uploaded = st.file_uploader("Choose a resume file (PDF, DOCX, TXT)", type=["pdf", "docx", "txt"])
    if uploaded is not None:
        with st.spinner(f"Parsing {uploaded.name}..."):
            files = {"file": (uploaded.name, uploaded.getvalue(), uploaded.type or "application/octet-stream")}
            data, err = api_post("/candidates/upload", files=files)
        if err:
            st.error(f"Upload failed: {err}")
        else:
            st.success("Resume parsed and saved!")
            col1, col2, col3 = st.columns(3)
            col1.metric("Name", data.get("name") or "—")
            col2.metric("Email", data.get("email") or "—")
            exp = data.get("experience_years")
            col3.metric("Experience", f"{exp:.1f} yrs" if exp is not None else "—")
            skills = data.get("skills") or []
            if skills:
                st.markdown("**Extracted skills:** " + " · ".join(f"`{s}`" for s in skills))

    st.divider()
    st.subheader("Recent Candidates")
    candidates, err = api_get("/candidates/")
    if err:
        st.error(err)
    elif not candidates:
        st.info("No candidates in the database yet.")
    else:
        for c in candidates[:20]:
            skills_str = ", ".join(c.get("skills") or []) or "—"
            with st.expander(f"#{c.get('id')} — {c.get('name') or 'Unknown'} ({c.get('email') or '—'})"):
                col1, col2, col3 = st.columns(3)
                col1.metric("Phone", c.get("phone") or "—")
                exp = c.get("experience_years")
                col2.metric("Experience", f"{exp:.1f} yrs" if exp is not None else "—")
                col3.metric("Source", c.get("source_file") or "—")
                st.markdown(f"**Skills:** {skills_str}")
                st.caption(f"Added: {str(c.get('created_at', ''))[:19]}")

# ── TAB 3: MATCH CANDIDATES ──────────────────────────────────────────────────
with tab_match:
    st.header("Match Candidates to a Vacancy")

    if "match_results" not in st.session_state:
        st.session_state.match_results = None
        st.session_state.match_error = None
        st.session_state.match_method = None

    vacancies_for_match, err_v = api_get("/vacancies/")
    if err_v:
        st.error(err_v)
    elif not vacancies_for_match:
        st.info("No vacancies available. Scrape some from hh.kz first.")
    else:
        vacancy_map = {f"[{v['id']}] {v['title']}": v["id"] for v in vacancies_for_match}
        col_left, col_right = st.columns([2, 1])
        with col_left:
            selected_label = st.selectbox("Select vacancy", options=list(vacancy_map.keys()))
            selected_job_id = vacancy_map[selected_label]
        with col_right:
            method = st.radio("Matching method", options=["funnel", "semantic", "tfidf", "llm"])
            top_k = st.slider("Top-K candidates", min_value=1, max_value=10, value=5)

        st.divider()
        if st.button("Find Top Candidates", type="primary", use_container_width=True):
            with st.spinner(f"Running {method} matching — top {top_k}..."):
                results_data, err_r = api_get(
                    "/recommendations/",
                    params={"job_id": selected_job_id, "method": method, "top_k": top_k},
                    timeout=180,
                )
            st.session_state.match_error = err_r
            st.session_state.match_results = results_data
            st.session_state.match_method = method

        if st.session_state.match_error:
            st.error(f"Matching failed: {st.session_state.match_error}")
        elif st.session_state.match_results is not None:
            results_data = st.session_state.match_results
            used_method = st.session_state.match_method
            match_results = results_data.get("results") or []
            if not match_results:
                st.info("No candidates matched. Upload resumes first.")
            else:
                st.success(f"Found {len(match_results)} candidate(s) via **{used_method}** method.")
                st.divider()
                for rank, item in enumerate(match_results, start=1):
                    cand = item.get("candidate") or {}
                    name = cand.get("name") or "Unknown"
                    email = cand.get("email") or "—"
                    tfidf_s = item.get("tfidf_score")
                    semantic_s = item.get("semantic_score")
                    llm_s = item.get("llm_score")
                    explanation = item.get("llm_explanation") or ""
                    strengths = item.get("strengths") or []
                    gaps = item.get("gaps") or []

                    with st.container():
                        st.markdown(f"### #{rank} — {name}")
                        c1, c2 = st.columns([1, 2])
                        with c1:
                            st.markdown(f"**Email:** {email}")
                            st.markdown(f"**Phone:** {cand.get('phone') or '—'}")
                            exp = cand.get("experience_years")
                            st.markdown(f"**Experience:** {f'{exp:.1f} yrs' if exp is not None else '—'}")
                            skills = cand.get("skills") or []
                            if skills:
                                st.markdown("**Skills:** " + " · ".join(f"`{s}`" for s in skills[:10]))
                        with c2:
                            if any(s is not None for s in [tfidf_s, semantic_s, llm_s]):
                                cols = st.columns(3)
                                if tfidf_s is not None:
                                    with cols[0]:
                                        score_bar("TF-IDF", tfidf_s)
                                if semantic_s is not None:
                                    with cols[1]:
                                        score_bar("Semantic", semantic_s)
                                if llm_s is not None:
                                    with cols[2]:
                                        score_bar("LLM", llm_s)

                        if explanation or strengths or gaps:
                            with st.expander("LLM Analysis — Strengths & Gaps"):
                                if explanation:
                                    st.markdown("**Explanation:**")
                                    st.write(explanation)
                                if strengths:
                                    st.markdown("**Strengths:**")
                                    for s in strengths:
                                        st.markdown(f"- {s}")
                                if gaps:
                                    st.markdown("**Gaps:**")
                                    for g in gaps:
                                        st.markdown(f"- {g}")
                        st.divider()

# ── TAB 4: STATUS ────────────────────────────────────────────────────────────
with tab_status:
    st.header("System Status")

    if st.button("Refresh Status"):
        st.rerun()

    health, err = api_get("/health", timeout=10)
    if err:
        st.error(f"Health check failed: {err}")
    else:
        st.success(f"API status: **{health.get('status', 'unknown').upper()}**")
        col1, col2, col3 = st.columns(3)
        col1.metric("Candidates in DB", health.get("candidate_count", 0))
        col2.metric("Vacancies in DB", health.get("vacancy_count", 0))
        last = health.get("last_email_poll") or "Never"
        col3.metric("Last Email Poll", str(last)[:19] if last != "Never" else "Never")

        poller = health.get("email_poller_running", False)
        if poller:
            st.info("Email poller is running.")
        else:
            st.warning("Email poller is not running (IMAP credentials not configured?).")

        st.divider()
        st.subheader("Raw Health Response")
        st.json({"api_url": API_URL, **health})
