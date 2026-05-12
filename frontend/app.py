"""Streamlit frontend for AI Recruiting Agent — Home Credit Bank."""

from __future__ import annotations

import os
import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="AI Рекрутинг — HCB",
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
        return None, f"Нет подключения к API: {API_URL}"
    except requests.exceptions.Timeout:
        return None, "Превышено время ожидания запроса"
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
        return None, f"Нет подключения к API: {API_URL}"
    except requests.exceptions.Timeout:
        return None, "Превышено время ожидания запроса"
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
    st.title("AI Рекрутинг")
    st.caption("Home Credit Bank — Внутренний инструмент")
    st.divider()
    st.markdown(f"**Бэкенд:** `{API_URL}`")

    health, _err = api_get("/health", timeout=5)
    if health:
        st.success(
            f"API работает — {health.get('candidate_count', 0)} кандидатов, "
            f"{health.get('vacancy_count', 0)} вакансий"
        )
    else:
        st.error("API недоступен")

    st.divider()
    st.markdown("**Синхронизация вакансий с hh.kz**")
    if st.button("Синхронизировать с hh.kz", use_container_width=True):
        with st.spinner("Загрузка с hh.kz — может занять 30–60 сек..."):
            data, err = api_post("/vacancies/scrape", json_data={}, timeout=300)
        if err:
            st.error(err)
        else:
            st.success(
                f"Готово: {data.get('imported', 0)} новых / "
                f"{data.get('total', 0)} всего вакансий."
            )


# ── Tabs ─────────────────────────────────────────────────────────────────────

tab_vacancies, tab_upload, tab_match, tab_status = st.tabs(
    ["Вакансии", "Загрузить резюме", "Подбор кандидатов", "Статус"]
)

# ── TAB 1: VACANCIES ─────────────────────────────────────────────────────────
with tab_vacancies:
    st.header("Список вакансий")
    st.caption("Вакансии загружены с hh.kz. Используйте кнопку в боковой панели для обновления.")

    vacancies, err = api_get("/vacancies/")
    if err:
        st.error(err)
    elif not vacancies:
        st.info("Вакансий пока нет. Нажмите «Синхронизировать с hh.kz» в боковой панели.")
    else:
        for v in vacancies:
            url = v.get("url") or ""
            link = f"[Открыть на hh.kz]({url})" if url else "—"
            with st.expander(f"#{v.get('id')} — {v.get('title', 'Без названия')}"):
                st.markdown(f"**Ссылка:** {link}")
                st.markdown(f"**Загружено:** {str(v.get('scraped_at', ''))[:19]}")
                meta = v.get("meta") or {}
                if meta:
                    cols = st.columns(3)
                    if exp := meta.get("experience"):
                        cols[0].markdown(f"**Опыт:** {exp}")
                    if sal := meta.get("salary"):
                        cols[1].markdown(f"**Зарплата:** {sal}")
                    if conds := meta.get("conditions"):
                        cols[2].markdown("**Условия:** " + " · ".join(conds))
                reqs = v.get("requirements") or []
                if reqs:
                    st.markdown("**Ключевые навыки:** " + " · ".join(f"`{r}`" for r in reqs))
                desc = v.get("description", "")
                if desc:
                    st.markdown("**Описание:**")
                    st.write(desc)
        st.caption(f"Всего: {len(vacancies)} вакансий")

# ── TAB 2: UPLOAD RESUME ─────────────────────────────────────────────────────
with tab_upload:
    st.header("Загрузить резюме")
    uploaded = st.file_uploader("Выберите файл резюме (PDF, DOCX, TXT)", type=["pdf", "docx", "txt"])
    if uploaded is not None:
        with st.spinner(f"Обработка {uploaded.name}..."):
            files = {"file": (uploaded.name, uploaded.getvalue(), uploaded.type or "application/octet-stream")}
            data, err = api_post("/candidates/upload", files=files)
        if err:
            st.error(f"Ошибка загрузки: {err}")
        else:
            st.success("Резюме обработано и сохранено!")
            col1, col2, col3 = st.columns(3)
            col1.metric("Имя", data.get("name") or "—")
            col2.metric("Email", data.get("email") or "—")
            exp = data.get("experience_years")
            col3.metric("Опыт", f"{exp:.1f} лет" if exp is not None else "—")
            skills = data.get("skills") or []
            if skills:
                st.markdown("**Извлечённые навыки:** " + " · ".join(f"`{s}`" for s in skills))

    st.divider()
    st.subheader("Недавние кандидаты")
    candidates, err = api_get("/candidates/")
    if err:
        st.error(err)
    elif not candidates:
        st.info("В базе данных пока нет кандидатов.")
    else:
        for c in candidates[:20]:
            skills = c.get("skills") or []
            exp = c.get("experience_years")
            with st.expander(f"#{c.get('id')} — {c.get('name') or 'Неизвестно'} ({c.get('email') or '—'})"):
                col1, col2, col3 = st.columns(3)
                col1.metric("Телефон", c.get("phone") or "—")
                col2.metric("Опыт", f"{exp:.1f} лет" if exp is not None else "—")
                col3.metric("Файл", c.get("source_file") or "—")
                if c.get("education"):
                    st.markdown(f"**Образование:** {c['education']}")
                if skills:
                    st.markdown("**Навыки:** " + " · ".join(f"`{s}`" for s in skills))
                else:
                    st.markdown("**Навыки:** —")
                if c.get("raw_text"):
                    with st.expander("Текст резюме, отправляемый на матчинг"):
                        st.text(c["raw_text"])
                st.caption(f"Добавлен: {str(c.get('created_at', ''))[:19]}")

# ── TAB 3: MATCH CANDIDATES ──────────────────────────────────────────────────
with tab_match:
    st.header("Подбор кандидатов на вакансию")

    if "match_results" not in st.session_state:
        st.session_state.match_results = None
        st.session_state.match_error = None
        st.session_state.match_method = None

    input_mode = st.radio(
        "Способ задания вакансии",
        options=["Выбрать из базы", "Ввести текст вакансии"],
        horizontal=True,
    )

    col_left, col_right = st.columns([2, 1])
    with col_right:
        method = st.radio("Метод подбора", options=["funnel", "semantic", "tfidf", "llm"])
        top_k = st.slider("Топ-K кандидатов", min_value=1, max_value=10, value=5)

    selected_job_id = None
    custom_vacancy_text = None

    if input_mode == "Выбрать из базы":
        vacancies_for_match, err_v = api_get("/vacancies/")
        if err_v:
            st.error(err_v)
        elif not vacancies_for_match:
            st.info("Вакансий нет. Сначала загрузите их с hh.kz.")
        else:
            vacancy_map = {f"[{v['id']}] {v['title']}": v["id"] for v in vacancies_for_match}
            with col_left:
                selected_label = st.selectbox("Выберите вакансию", options=list(vacancy_map.keys()))
                selected_job_id = vacancy_map[selected_label]
    else:
        with col_left:
            custom_vacancy_text = st.text_area(
                "Текст вакансии",
                placeholder="Вставьте описание вакансии, требования к кандидату...",
                height=200,
            )

    st.divider()
    can_run = (selected_job_id is not None) or (custom_vacancy_text and custom_vacancy_text.strip())
    if st.button("Найти лучших кандидатов", type="primary", use_container_width=True, disabled=not can_run):
        params: dict = {"method": method, "top_k": top_k}
        if selected_job_id is not None:
            params["job_id"] = selected_job_id
        else:
            params["vacancy_text"] = custom_vacancy_text.strip()
        with st.spinner(f"Запуск подбора методом «{method}» — топ {top_k}..."):
            results_data, err_r = api_get(
                "/recommendations/",
                params=params,
                timeout=180,
            )
            st.session_state.match_error = err_r
            st.session_state.match_results = results_data
            st.session_state.match_method = method

        if st.session_state.match_error:
            st.error(f"Ошибка подбора: {st.session_state.match_error}")
        elif st.session_state.match_results is not None:
            results_data = st.session_state.match_results
            used_method = st.session_state.match_method
            match_results = results_data.get("results") or []
            if not match_results:
                st.info("Кандидаты не найдены. Сначала загрузите резюме.")
            else:
                st.success(f"Найдено {len(match_results)} кандидат(ов) методом **{used_method}**.")
                st.divider()
                for rank, item in enumerate(match_results, start=1):
                    cand = item.get("candidate") or {}
                    name = cand.get("name") or "Неизвестно"
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
                            st.markdown(f"**Телефон:** {cand.get('phone') or '—'}")
                            exp = cand.get("experience_years")
                            st.markdown(f"**Опыт:** {f'{exp:.1f} лет' if exp is not None else '—'}")
                            skills = cand.get("skills") or []
                            if skills:
                                st.markdown("**Навыки:** " + " · ".join(f"`{s}`" for s in skills[:10]))
                        with c2:
                            if any(s is not None for s in [tfidf_s, semantic_s, llm_s]):
                                cols = st.columns(3)
                                if tfidf_s is not None:
                                    with cols[0]:
                                        score_bar("TF-IDF", tfidf_s)
                                if semantic_s is not None:
                                    with cols[1]:
                                        score_bar("Семантика", semantic_s)
                                if llm_s is not None:
                                    with cols[2]:
                                        score_bar("LLM", llm_s)

                        if explanation or strengths or gaps:
                            with st.expander("Анализ LLM — сильные стороны и пробелы"):
                                if explanation:
                                    st.markdown("**Пояснение:**")
                                    st.write(explanation)
                                if strengths:
                                    st.markdown("**Сильные стороны:**")
                                    for s in strengths:
                                        st.markdown(f"- {s}")
                                if gaps:
                                    st.markdown("**Пробелы:**")
                                    for g in gaps:
                                        st.markdown(f"- {g}")

                        raw_text = cand.get("raw_text") or ""
                        if raw_text:
                            with st.expander("Текст резюме, отправленный на матчинг"):
                                st.text(raw_text)

                        st.divider()

# ── TAB 4: STATUS ────────────────────────────────────────────────────────────
with tab_status:
    st.header("Статус системы")

    if st.button("Обновить"):
        st.rerun()

    health, err = api_get("/health", timeout=10)
    if err:
        st.error(f"Ошибка проверки состояния: {err}")
    else:
        st.success(f"Статус API: **{health.get('status', 'unknown').upper()}**")
        col1, col2, col3 = st.columns(3)
        col1.metric("Кандидатов в БД", health.get("candidate_count", 0))
        col2.metric("Вакансий в БД", health.get("vacancy_count", 0))
        last = health.get("last_email_poll") or "Никогда"
        col3.metric("Последний опрос почты", str(last)[:19] if last != "Никогда" else "Никогда")

        poller = health.get("email_poller_running", False)
        if poller:
            st.info("Опрос почты активен.")
        else:
            st.warning("Опрос почты не запущен (не настроены IMAP-данные?).")

        st.divider()
        st.subheader("Ответ сервера")
        st.json({"api_url": API_URL, **health})
