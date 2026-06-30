"""femrep.locale_ru — Russian string layer for the ГОСТ 7.32-2017 report profile.

Every visible label, verdict, and the auto-generated реферат / введение /
заключение prose lives here so report_gost_docx emits a fully Russian document.
Proper nouns (Ansys, Nastran, femis), the abbreviation GCI, unit symbols, and
file names are intentionally kept; everything else is Russian.
"""
from __future__ import annotations

# Structural elements of the report (ГОСТ 7.32-2017 §6), as headings.
STRUCT = {
    "referat": "РЕФЕРАТ",
    "soderzhanie": "СОДЕРЖАНИЕ",
    "vvedenie": "ВВЕДЕНИЕ",
    "zaklyuchenie": "ЗАКЛЮЧЕНИЕ",
    "osnovnaya": "ОСНОВНАЯ ЧАСТЬ",
}

# Титульный лист labels.
TITLE = {
    "report_kind": "ОТЧЁТ О НАУЧНО-ИССЛЕДОВАТЕЛЬСКОЙ РАБОТЕ",
    "udc": "УДК",
    "approve": "УТВЕРЖДАЮ",
    "head_org": "Руководитель организации",
    "head_work": "Руководитель НИР",
    "signature": "подпись",
    "date": "дата",
    "report_type_final": "(заключительный)",
    "report_type_interim": "(промежуточный)",
}

# Основная часть — Russian section titles, keyed by the section registry keys.
SECTION_TITLES_RU = {
    "summary": "Сводка результатов",
    "model": "Расчётная модель",
    "meshing": "Конечно-элементная сетка",
    "composites": "Композиционные материалы",
    "solve": "Решение и сходимость",
    "results": "Результаты расчёта",
    "gci": "Оценка сеточной сходимости (GCI)",
    "governance": "Контроль качества (femis)",
    "manifest": "Протокол вычислений и происхождение данных",
}

# Table headers used across sections.
HDR = {
    "param": "Параметр",
    "value": "Значение",
    "element": "Элемент",
    "count": "Количество",
    "metric": "Показатель",
    "criterion": "Критерий",
    "conclusion": "Вывод",
    "note": "Примечание",
    "evidence": "Свидетельство",
    "state": "Состояние",
}

# Gate names (govern gate keys) → Russian.
GATE_NAMES = {
    "units": "Единицы измерения",
    "thermal_connectivity": "Связность тепловой модели",
    "equilibrium_heat_balance": "Равновесие / тепловой баланс",
    "convergence": "Сходимость решения",
    "singularity_check": "Контроль сингулярностей",
    "mesh_independence_GCI": "Сеточная независимость (GCI)",
}

# Readiness item keys → Russian.
READINESS_NAMES = {
    "result_hash": "Контрольная сумма файла результатов",
    "deck_hash": "Контрольная сумма расчётной модели",
    "convergence": "Сходимость",
    "mesh_independence": "Сеточная независимость",
    "geometry": "Геометрия",
}

_VERDICT = {"pass": "соответствует", "fail": "не соответствует", "not_done": "не выполнено"}
_STATUS = {"complete": "полное", "missing": "отсутствует", "blocked": "заблокировано",
           "warning": "с замечаниями", "not_applicable": "неприменимо"}
_READINESS_STATUS = {
    "ready_to_issue": "Готов к выпуску: необходимые свидетельства полны.",
    "issue_with_limitations": "Выпускается с ограничениями: отчёт прослеживаем, "
                              "но часть верификационных свидетельств отсутствует.",
    "blocked": "Заблокировано: не пройден хотя бы один критерий или свидетельство.",
}
_ANALYSIS = {"thermal": "тепловой", "structural": "прочностной",
             "static": "прочностной", "modal": "модальный"}
_QOI = {
    "temperature": "температура",
    "von_mises_stress": "эквивалентные напряжения (по Мизесу)",
    "displacement_magnitude": "перемещения (модуль)",
}
_UNITS = {"K": "К", "Pa": "Па", "m": "м", "mm": "мм", "SI": "СИ"}


def verdict_ru(v: str) -> str:
    return _VERDICT.get(v, v)


def status_ru(s: str) -> str:
    return _STATUS.get(s, s)


def readiness_status_ru(status: str, fallback: str = "") -> str:
    return _READINESS_STATUS.get(status, fallback or status)


def analysis_ru(analysis_type: str) -> str:
    """Map a manifest analysis_type ('thermal', 'structural', 'steady_thermal …')
    to a Russian adjective; first matching token wins."""
    low = (analysis_type or "").lower()
    for key, ru in _ANALYSIS.items():
        if key in low:
            return ru
    return "расчётный"


def qoi_ru(name: str) -> str:
    return _QOI.get(name, name)


def units_ru(u: str) -> str:
    return _UNITS.get((u or "").strip(), u)


_UNIT_TOKENS = {"SI": "СИ", "m": "м", "kg": "кг", "s": "с", "K": "К", "N": "Н",
                "Pa": "Па", "W": "Вт", "mm": "мм", "A": "А", "mol": "моль", "cd": "кд"}


def solver_line_ru(manifest: dict) -> str:
    """Russian 'решатель + версия' cell. The solver name is a proper noun (first
    token, e.g. Nastran/Ansys); the version is kept only when it looks like a real
    version number, otherwise the honest English placeholder ('version not in .f06
    …') is replaced with «версия не определена» so no English prose leaks."""
    import re
    name = (manifest.get("solver") or "—").split()
    name = name[0].capitalize() if name else "—"
    ver = (manifest.get("solver_version") or "").strip()
    if not re.match(r"^[\dvVвВ]?\d", ver):     # not a real version token
        ver = "версия не определена"
    return f"{name}, {ver}"


def units_full_ru(s: str) -> str:
    """Transliterate a units string like 'SI (m, kg, s, K, N, Pa, W)' token-by-token
    into Russian: 'СИ (м, кг, с, К, Н, Па, Вт)'. Unknown tokens pass through."""
    import re
    return re.sub(r"[A-Za-z]+", lambda m: _UNIT_TOKENS.get(m.group(0), m.group(0)), s or "")


def _qoi_phrase(results: dict) -> tuple[str, str, str]:
    q = results.get("primary_qoi", {})
    name = qoi_ru(q.get("name", ""))
    units = units_ru(q.get("units", ""))
    rng = f"{q.get('min', '')}…{q.get('max', '')} {units}".strip()
    return name, units, rng


def keywords(results: dict, manifest: dict) -> list[str]:
    """Ключевые слова for the реферат (ГОСТ 7.32 §6.3: 5–15, uppercase)."""
    name, _, _ = _qoi_phrase(results)
    base = ["конечно-элементный расчёт", "метод конечных элементов",
            analysis_ru(manifest.get("analysis_type", "")) + " анализ",
            name, "верификация", "прослеживаемость"]
    return [w.upper() for w in base if w and w.strip()]


def referat_text(results: dict, manifest: dict) -> str:
    """Текст реферата: объект/цель/методы/результаты (ГОСТ 7.32 §6.3). Объёмную
    строку (страниц/рисунков/таблиц/источников) формирует рендерер полем NUMPAGES."""
    name, units, rng = _qoi_phrase(results)
    solver = (manifest.get("solver", "").split() or ["—"])[0].capitalize()
    return (
        f"Объект исследования — конечно-элементная модель; вид анализа — "
        f"{analysis_ru(manifest.get('analysis_type',''))}. Контролируемая величина — "
        f"{name}, её значения лежат в диапазоне {rng}. Расчёт выполнен решателем "
        f"{solver}; файлы результатов получены вне настоящей работы и в отчёте "
        f"обрабатываются. Каждое приведённое число связано с исходной моделью и "
        f"файлом результатов контрольными суммами. Критерии качества — единицы "
        f"измерения, связность модели, сходимость решения, сеточная независимость — "
        f"вычислены по данным расчёта; невыполненные критерии указаны явно."
    )


def vvedenie_text(results: dict, manifest: dict) -> str:
    name, _, rng = _qoi_phrase(results)
    return (
        f"Конечно-элементный расчёт даёт дискретное поле контролируемой величины; "
        f"её достоверность определяется идеализацией модели, граничными условиями, "
        f"сходимостью решения и независимостью результата от сетки. Настоящий отчёт "
        f"фиксирует перечисленные свидетельства для выполненного расчёта и связывает "
        f"каждое число с исходными файлами. В основной части последовательно рассмотрены "
        f"расчётная модель и сетка, решение и его сходимость, результаты, оценка "
        f"сеточной сходимости и критерии качества; происхождение данных приведено в "
        f"протоколе вычислений."
    )


def zaklyuchenie_text(results: dict, checks: dict) -> str:
    name, units, rng = _qoi_phrase(results)
    readiness = checks.get("readiness") or {}
    verdict = readiness_status_ru(readiness.get("status", ""),
                                  "Отчёт сформирован.")
    gates = checks.get("gates", [])
    n_pass = sum(1 for g in gates if g.get("verdict") == "pass")
    n_total = len(gates)
    return (
        f"Контролируемая величина «{name}» в проведённом расчёте лежит в диапазоне "
        f"{rng}. Из {n_total} критериев качества выполнено {n_pass}; невыполненные "
        f"критерии перечислены в разделе контроля качества и определяют область "
        f"применимости результата. {verdict} Приёмку результата выполняет "
        f"квалифицированный специалист; отчёт предоставляет для этого свидетельства, "
        f"но инженерного решения не заменяет."
    )


def review_summary_ru(results: dict, checks: dict) -> str:
    """One-line Russian summary for the GUI review pane (govern's claim is English)."""
    name, units, rng = _qoi_phrase(results)
    readiness = checks.get("readiness") or {}
    st = readiness_status_ru(readiness.get("status", ""), "отчёт сформирован")
    label = name[:1].upper() + name[1:] if name else "Величина"
    return f"{label}: диапазон {rng}. {st}"


def gate_note_ru(gate: dict, gci: dict | None) -> str:
    """Russian note per gate (we re-derive rather than reuse govern's English note)."""
    key, verdict = gate.get("gate"), gate.get("verdict")
    if key == "units":
        return "Приняты единицы СИ; контрольный расчёт размерностей не выполнялся."
    if key == "thermal_connectivity":
        return ("Распределение температуры присутствует — тела связаны." if verdict == "pass"
                else "Единая температура по модели — признак изолированных тел.")
    if key == "equilibrium_heat_balance":
        return "Требует извлечения реакций / тепловых потоков; в файле результатов отсутствует."
    if key == "convergence":
        return {"pass": "Решение сошлось по данным журнала.",
                "fail": "В журнале решения присутствует маркёр остановки / ошибки.",
                "not_done": "Журнал решения не предоставлен."}.get(verdict, "")
    if key == "singularity_check":
        return "Контролируемая величина — узловое поле; исключение сингулярного пика требует сравнения сеток."
    if key == "mesh_independence_GCI":
        if gci:
            return (f"GCI(мелкая) {gci.get('gci_fine_pct', 0):.3f} %, "
                    f"R {gci.get('convergence_ratio_R', 0):.3f}, "
                    f"p {gci.get('observed_order_p', 0):.3f}.")
        return "Одна сетка — GCI не выполнялся; внутрирегиональный градиент даёт оценку сверху."
    return ""


def readiness_note_ru(item: dict) -> str:
    key, status = item.get("key"), item.get("status")
    table = {
        "result_hash": {"complete": "Контрольная сумма файла результатов зафиксирована.",
                        "missing": "Контрольная сумма файла результатов отсутствует."},
        "deck_hash": {"complete": "Контрольная сумма расчётной модели зафиксирована.",
                      "missing": "Расчётная модель не предоставлена или не хешируется."},
        "convergence": {"complete": "Свидетельство сходимости присутствует.",
                        "blocked": "Обнаружена несходимость решения.",
                        "missing": "Свидетельство сходимости отсутствует."},
        "mesh_independence": {"complete": "Исследование сеточной сходимости пройдено.",
                              "warning": "Исследование сеточной сходимости с замечаниями.",
                              "missing": "Исследование сеточной сходимости не предоставлено."},
        "geometry": {"complete": "Геометрия доступна для построения полей.",
                     "not_applicable": "Табличные результаты без геометрии модели."},
    }
    return table.get(key, {}).get(status, status_ru(status))


# --- GUI (PySide6 desktop app) strings ---------------------------------------
# Centralized here so gui.py holds no hardcoded label text and a zero-English
# test can scan a single source. Proper nouns (femrep/femis/Ansys/Nastran) and
# abbreviations (GCI/QoI/PDF/DOCX) are intentionally kept.

# Built-in entries always present in the main-window «Шаблон» dropdown.
BUILTIN_DEFAULT_LABEL = "По умолчанию"
BUILTIN_GOST_LABEL = "ГОСТ 7.32-2017 (DOCX, рус.)"

# Branding / title-block field labels (template editor). Keys mirror
# templates.DEFAULT_BRANDING; unknown keys pass through unchanged.
BRANDING_LABELS = {
    "title": "Название",
    "author": "Автор",
    "company": "Организация",
    "project": "Проект",
    "customer": "Заказчик",
    "document_number": "Номер документа",
    "revision": "Редакция",
    "prepared_by": "Подготовил",
    "checked_by": "Проверил",
    "approved_by": "Утвердил",
    "logo": "Логотип",
    "color_primary": "Основной цвет",
    "color_accent": "Акцентный цвет",
    "color_warn": "Цвет предупреждения",
    "color_ok": "Цвет «норма»",
    "color_muted": "Приглушённый цвет",
    "font": "Шрифт",
    "page_size": "Размер страницы",
    "ministry": "Министерство (ведомство)",
    "udc": "УДК",
    "city": "Город",
    "year": "Год",
    "report_type": "Вид отчёта",
    "head_org_title": "Должность руководителя организации",
    "head_work_title": "Должность руководителя НИР",
}


def branding_label(key: str) -> str:
    return BRANDING_LABELS.get(key, key)


GUI = {
    # window / brand
    "window_title": "femrep — генератор отчётов по МКЭ под управлением femis",
    "brand_sub": "FEM-отчёты под femis",
    "rail_hint": "femis: вывод не сильнее своей проверки.",
    # step / card titles
    "step_result": "Результат",
    "step_check": "Проверка",
    "step_template": "Шаблон",
    "step_export": "Экспорт",
    # step 1 (result)
    "card1_sub": "Перетащите сюда любые файлы — результат, журнал, сетки GCI "
                 "или расчётную модель. Роль определяется автоматически.",
    "sec_attachments": "Вложения",
    "drop_text": "Перетащите файлы или нажмите, чтобы выбрать\n"
                 "результат · журнал · GCI · расчётная модель",
    "attach_required": "файл результата обязателен (.rst / .rth / .f06 / .op2)",
    "attach_ready": "готово к извлечению",
    "with_figures": "С иллюстрациями",
    "btn_extract": "Извлечь и проверить →",
    "attach_remove_tip": "Убрать",
    # step 2 (check)
    "card2_sub": "Результаты извлечены. Проверьте величину интереса и вердикты "
                 "проверок femis перед выпуском отчёта.",
    "sec_contour": "Контур",
    "preview_placeholder": "предпросмотр контура появится после извлечения",
    "sec_qoi": "Сводка показателей",
    "sec_gates": "Проверки femis",
    "sec_claim": "Утверждение femis",
    "contour_unavailable": "контур недоступен",
    "contour_unavailable_hint": "контур недоступен — см. историю по времени в отчёте",
    "btn_open_review": "Открыть HTML-обзор",
    "btn_next": "Далее →",
    "btn_back": "Назад",
    # step 3 (template)
    "card3_sub": "Проект и шаблон задают брендинг, разделы и профиль (например, ГОСТ).",
    "sec_project": "Проект",
    "btn_open_project": "Открыть / создать проект…",
    "btn_open_project_tip": "Открыть или создать папку проекта femrep с шаблонами",
    "project_none": "проект не выбран — встроенная разметка",
    "sec_template": "Шаблон оформления",
    "btn_manage_templates": "Управление шаблонами…",
    "sec_content": "Содержание отчёта (что попадёт в отчёт)",
    "avail_yes": "доступно",
    "avail_example": "контрольный пример",
    "avail_no_gci": "нет данных GCI",
    # step 4 (export)
    "card4_sub": "Сводка форматирования. Нажмите, чтобы сгенерировать итоговый отчёт.",
    "sec_summary": "Сводка",
    "sec_sections": "Разделы отчёта",
    "sections_none": "разделы не выбраны",
    "sec_format": "Формат",
    "gost_note": "Профиль ГОСТ — отчёт будет сохранён как русский .docx "
                 "(формат выбран автоматически).",
    "btn_generate": "Сгенерировать отчёт",
    "export_project": "Проект",
    "export_template": "Шаблон",
    "export_profile": "Профиль",
    "profile_default_name": "стандартный",
    # status
    "status_running": "выполняется…",
    "status_done": "готово",
    "status_error": "ОШИБКА",
    # dialogs / messages (modal — covered by the string-level test)
    "dlg_attach_files": "Выберите файлы",
    "filter_all": "Все файлы (*.*)",
    "dlg_open_project": "Открыть или создать папку проекта femrep",
    "dlg_save_report": "Сохранить отчёт",
    "filter_report": "Отчёт (*{ext})",
    "msg_attach_first": "Сначала прикрепите файл результатов.",
    "msg_extract_first": "Сначала извлеките результаты (шаг 1).",
    "msg_open_project_first": "Сначала откройте проект, чтобы хранить шаблоны.",
    "msg_load_template_failed": "Не удалось загрузить шаблон {name}: {err}",
    "msg_report_saved": "Отчёт сохранён:\n{path}",
    "msg_render_failed": "Не удалось сформировать отчёт:\n{err}",
    "startup_error_title": "femrep — ошибка запуска",
    "startup_error_body": "{tb}\n\nЛог: {path}",
    # template editor (dialog)
    "td_title": "femrep — шаблоны отчёта",
    "td_list_header": "Шаблоны в этом проекте:",
    "td_new_blank": "Создать пустой",
    "td_new_from_result": "Создать из результата…",
    "td_duplicate": "Дублировать",
    "td_delete": "Удалить",
    "td_name": "Название",
    "td_profile": "Профиль",
    "profile_default_label": "Стандартный (PDF/DOCX)",
    "profile_gost_label": "ГОСТ 7.32-2017 (DOCX, рус.)",
    "td_branding_header": "Брендинг / титульный блок:",
    "td_sections_header": "Разделы (отметьте для включения, порядок — кнопками ↑/↓):",
    "td_intro": "Вступление:",
    "td_intro_placeholder": "необязательный текст под заголовком раздела",
    "td_save": "Сохранить шаблон",
    "td_copy_suffix": "копия",
    "td_new_template_title": "Новый шаблон",
    "td_new_template_prompt": "Название шаблона:",
    "td_new_template_default": "Новый шаблон",
    "td_default_template_name": "По умолчанию",
    "td_seed_result_title": "Файл результата для основы шаблона",
    "filter_results": "Результаты (*.rst *.rth *.f06 *.op2);;Все файлы (*.*)",
    "td_seed_failed": "Не удалось прочитать результат для основы шаблона:\n{err}",
    "td_logo_title": "Изображение логотипа",
    "filter_images": "Изображения (*.png *.jpg *.jpeg)",
    "td_saved": "Шаблон сохранён:\n{path}",
    "td_delete_confirm": "Удалить шаблон {name}?",
    "td_from_result_name": "Из результата",
}
