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
_ANALYSIS = {"thermal": "тепловой", "structural": "прочностной"}
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
    body = (
        f"Объект исследования — конечно-элементная модель, "
        f"{analysis_ru(manifest.get('analysis_type',''))} анализ. "
        f"Цель работы — формирование прослеживаемого и защищаемого отчёта по "
        f"результатам расчёта с фиксацией происхождения данных и проверкой "
        f"критериев качества. В качестве основной контролируемой величины "
        f"принята величина «{name}»; диапазон значений составил {rng}. "
        f"Расчёт выполнен решателем {manifest.get('solver','')} "
        f"{manifest.get('solver_version','')}. Каждое числовое значение увязано "
        f"с исходной моделью и файлом результатов через контрольные суммы; "
        f"выводы по критериям вычислены, а не назначены."
    )
    return body


def vvedenie_text(results: dict, manifest: dict) -> str:
    name, _, rng = _qoi_phrase(results)
    return (
        f"Настоящий отчёт содержит результаты {analysis_ru(manifest.get('analysis_type',''))} "
        f"конечно-элементного расчёта и свидетельства их достоверности. "
        f"Отчёт является документом-регистратором: он не управляет решателем, а "
        f"обрабатывает уже полученные файлы результатов, обеспечивая их "
        f"прослеживаемость. Основная контролируемая величина — «{name}» "
        f"(диапазон {rng}). В основной части приведены модель, сетка, решение и "
        f"его сходимость, результаты, оценка сеточной сходимости и контроль "
        f"качества; происхождение данных зафиксировано в протоколе вычислений."
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
        f"По результатам расчёта основная контролируемая величина «{name}» "
        f"находится в диапазоне {rng}. Из {n_total} критериев качества выполнено "
        f"{n_pass}. {verdict} Отчёт допускается к выпуску квалифицированным "
        f"специалистом; настоящий документ собирает свидетельства, но не "
        f"заменяет инженерную приёмку."
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
