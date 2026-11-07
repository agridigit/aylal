"""Registry export rendering (R6): the same rows and columns in PDF and XLSX, French / Arabic / darija, RTL aware.

Self-contained on purpose (stdlib, reportlab, openpyxl, arabic-reshaper, python-bidi): the worker image does not
embed `app`, so this file and `fonts/` are copied into it at build time. Fonts are IBM Plex Sans (SIL OFL 1.1), shipped
in the repository and embedded in every PDF; nothing is fetched at runtime.
"""
import hashlib
import io
import json
import uuid
from pathlib import Path
from typing import Any

import arabic_reshaper
from bidi import get_display
from openpyxl import Workbook
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

MAX_ROWS = 10_000
COLUMNS = ("date", "parcel", "crop", "product", "active_ingredient", "dose", "area_ha", "operator", "warnings", "unchecked", "corrected")
_FONTS = Path(__file__).resolve().parent / "fonts"
_RTL = frozenset({"ar", "ary"})

LABELS: dict[str, dict[str, str]] = {
    "fr": dict(zip(COLUMNS, ("Date", "Parcelle", "Culture", "Produit", "Matière active", "Dose", "Surface (ha)", "Opérateur",
                             "Avertissements", "Non contrôlé", "Écriture corrigée"), strict=True)),
    "ar": dict(zip(COLUMNS, ("التاريخ", "القطعة", "الزراعة", "المنتوج", "المادة الفعالة", "الجرعة", "المساحة (هكتار)", "المشغّل",
                             "التحذيرات", "غير مراقب", "مصحَّح"), strict=True)),
    "ary": dict(zip(COLUMNS, ("التاريخ", "القطعة", "الزرع", "المنتوج", "المادة الفعالة", "الجرعة", "المساحة (هكتار)", "العامل",
                              "التنبيهات", "ما تّشافش", "تصحّح"), strict=True)),
}
WARNING_LABELS: dict[str, dict[str, str]] = {
    "fr": {
        "not_authorized_for_crop": "Produit non autorisé sur cette culture",
        "dose_above_max": "Dose supérieure au maximum homologué",
        "max_applications_reached": "Nombre maximal d'applications atteint",
        "dar_unknown": "Délai avant récolte inconnu",
        "free_product_unchecked": "Produit libre non contrôlé",
    },
    "ar": {
        "not_authorized_for_crop": "منتوج غير مرخص لهذه الزراعة",
        "dose_above_max": "الجرعة أعلى من الحد الأقصى المرخص",
        "max_applications_reached": "تم بلوغ الحد الأقصى لعدد المعالجات",
        "dar_unknown": "مدة ما قبل الحصاد غير معروفة",
        "free_product_unchecked": "منتوج حر غير مراقب",
    },
    "ary": {
        "not_authorized_for_crop": "المنتوج ماشي مسموح فهاد الزرع",
        "dose_above_max": "الجرعة كتفوت الحد الأقصى",
        "max_applications_reached": "وصلتي للعدد الأقصى د المعالجات",
        "dar_unknown": "مدة الانتظار قبل الجني ماعروفاش",
        "free_product_unchecked": "منتوج حر ما تّشافش",
    },
}
YES_NO: dict[str, tuple[str, str]] = {"fr": ("Oui", "Non"), "ar": ("نعم", "لا"), "ary": ("إيه", "لا")}
TITLES = {"fr": "Registre phytosanitaire", "ar": "سجل المعالجات الفلاحية", "ary": "سجل المعالجات الفلاحية"}
_FOOTER_WORDS = {"fr": ("Ferme", "Période", "Généré le", "Catalogue", "Page"), "ar": ("الضيعة", "الفترة", "أنشئ في", "الكتالوج", "صفحة"),
                 "ary": ("الضيعة", "الفترة", "تصاد في", "الكتالوج", "صفحة")}


def is_rtl(lang: str) -> bool:
    return lang in _RTL


def shape_arabic(value: str) -> str:
    """Join the letters and reorder for visual display (PDF engines draw glyphs left to right)."""
    return str(get_display(arabic_reshaper.reshape(value)))


def font_path(lang: str) -> str:
    return str(_FONTS / ("IBMPlexSansArabic-Regular.ttf" if is_rtl(lang) else "IBMPlexSans-Regular.ttf"))


def export_key(farm_id: uuid.UUID, job_id: uuid.UUID, fmt: str) -> str:
    """Object key chosen by the server only: farms/{farm}/exports/{job}/registry.{pdf|xlsx}."""
    return f"farms/{farm_id}/exports/{job_id}/registry.{fmt}"


def _number(value: Any) -> str:
    return f"{float(value):g}"


def _warnings(raw: Any, lang: str) -> str:
    if isinstance(raw, str):
        raw = json.loads(raw)
    labels = WARNING_LABELS[lang]
    return "; ".join(labels.get(w.get("code", ""), str(w.get("code", ""))) for w in raw or [])


def _ingredients(raw: Any) -> str:
    if isinstance(raw, str):
        raw = json.loads(raw)
    return ", ".join(" ".join(p for p in (str(i.get("name") or ""), str(i.get("concentration") or "")) if p) for i in raw or [])


def entry_to_row(entry: dict[str, Any], lang: str) -> dict[str, Any]:
    """One registry entry as a flat row of display values (identical for PDF and XLSX)."""
    yes, no = YES_NO[lang]
    day = entry["performed_on"]
    dose = entry.get("dose")
    return {
        "date": day.isoformat() if hasattr(day, "isoformat") else str(day),
        "parcel": entry.get("parcel_name") or "",
        "crop": entry.get("crop_name") or "",
        "product": entry.get("product_name") or "",
        "active_ingredient": _ingredients(entry.get("active_ingredients")),
        "dose": "" if dose is None else f"{_number(dose)} {entry.get('dose_unit') or ''}".strip(),
        "area_ha": None if entry.get("area_ha") is None else round(float(entry["area_ha"]), 4),
        "operator": entry.get("operator_name") or "",
        "warnings": _warnings(entry.get("warnings"), lang),
        "unchecked": yes if entry.get("is_free_product") else no,
        "corrected": yes if entry.get("corrected") else no,
    }


def content_sha256(rows: list[dict[str, Any]]) -> str:
    """Fingerprint of the exported values (printed in the footer of both files)."""
    blob = json.dumps(list(rows), sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


def _check_cap(rows: Any) -> None:
    if len(rows) > MAX_ROWS:
        raise ValueError("export_too_large")


def _footer_text(lang: str, meta: dict[str, Any], digest: str) -> str:
    farm, period, generated, catalogue, _ = _FOOTER_WORDS[lang]
    return (
        f"{farm}: {meta['farm_name']} | {period}: {meta['period_from'].isoformat()} - {meta['period_to'].isoformat()}"
        f" | {generated}: {meta['generated_at'].date().isoformat()} | {catalogue}: {meta['catalog_version']} | SHA-256: {digest}"
    )


def _safe_text(value: Any) -> Any:
    """A text cell that could be read as a formula is stored with a leading apostrophe."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def render_xlsx(rows: list[dict[str, Any]], *, lang: str, meta: dict[str, Any]) -> bytes:
    _check_cap(rows)
    digest = content_sha256(rows)
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = TITLES[lang][:31]
    ws.sheet_view.rightToLeft = is_rtl(lang)
    ws.append([LABELS[lang][c] for c in COLUMNS])
    for row in rows:
        ws.append([_safe_text(row[c]) for c in COLUMNS])
    ws.freeze_panes = "A2"
    for letter, width in zip("ABCDEFGHIJK", (12, 22, 16, 22, 24, 12, 12, 16, 40, 12, 14), strict=True):
        ws.column_dimensions[letter].width = width
    ws.oddFooter.center.text = _footer_text(lang, {**meta, "farm_name": str(meta["farm_name"]).replace("&", "&&")[:60]}, digest)[:250]
    ws.oddFooter.center.size = 7
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


_WIDTHS = (52, 95, 62, 95, 95, 60, 52, 62, 110, 52, 62)
_SIZE, _LEAD, _PAD, _MARGIN = 7.0, 8.5, 3.0, 15.0


def _register(lang: str) -> str:
    name = "AylalArabic" if is_rtl(lang) else "AylalSans"
    if name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(name, font_path(lang)))
    return name


def _wrap(value: str, font: str, width: float, rtl: bool) -> list[str]:
    def measure(s: str) -> float:
        width: float = pdfmetrics.stringWidth(shape_arabic(s) if rtl else s, font, _SIZE)
        return width

    lines: list[str] = []
    current = ""
    for word in value.split():
        trial = f"{current} {word}".strip()
        if measure(trial) <= width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
        while measure(current) > width and len(current) > 1:  # a word wider than the column (hash, long name)
            cut = len(current)
            while cut > 1 and measure(current[:cut]) > width:
                cut -= 1
            lines.append(current[:cut])
            current = current[cut:]
    return [*lines, current] if current or not lines else lines


def render_pdf(rows: list[dict[str, Any]], *, lang: str, meta: dict[str, Any]) -> bytes:
    _check_cap(rows)
    digest = content_sha256(rows)
    font, rtl = _register(lang), is_rtl(lang)
    page_w, page_h = (float(v) for v in landscape(A4))
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(page_w, page_h), initialFontName=font, initialFontSize=_SIZE, initialLeading=_LEAD)
    pdf.setTitle(TITLES[lang])
    shown = (lambda s: shape_arabic(s)) if rtl else (lambda s: s)
    xs: list[float] = []
    x = _MARGIN
    for w in _WIDTHS:
        xs.append(x)
        x += w
    if rtl:
        xs = [page_w - cx - w for cx, w in zip(xs, _WIDTHS, strict=True)]
    labels = [LABELS[lang][c] for c in COLUMNS]
    head_size = min([_SIZE] + [(_WIDTHS[i] - 2 * _PAD) / max(pdfmetrics.stringWidth(shown(lab), font, 1), 1) for i, lab in enumerate(labels)])
    footer = _footer_text(lang, meta, digest)
    state = {"page": 0}

    def draw(text: str, i: int, y: float, size: float = _SIZE) -> None:
        pdf.setFont(font, size)
        if rtl:
            pdf.drawRightString(xs[i] + _WIDTHS[i] - _PAD, y, shown(text))
        else:
            pdf.drawString(xs[i] + _PAD, y, text)

    def new_page() -> float:
        if state["page"]:
            pdf.showPage()
        state["page"] += 1
        top = page_h - _MARGIN
        pdf.setFont(font, 11)
        title = shown(TITLES[lang])
        (pdf.drawRightString(page_w - _MARGIN, top - 9, title) if rtl else pdf.drawString(_MARGIN, top - 9, title))
        y = top - 24
        for i, lab in enumerate(labels):
            draw(lab, i, y - 8, head_size)
        pdf.setLineWidth(0.6)
        pdf.line(_MARGIN, y - 11, page_w - _MARGIN, y - 11)
        pdf.setFont(font, 5.5)
        pdf.drawString(_MARGIN, 10, shown(footer) if rtl else footer)
        pdf.drawRightString(page_w - _MARGIN, 10, f"{_FOOTER_WORDS[lang][4]} {state['page']}" if not rtl else shown(f"{_FOOTER_WORDS[lang][4]} {state['page']}"))
        return y - 13

    y = new_page()
    bottom = 22.0
    for row in rows:
        cells = [_wrap("" if row[c] is None else str(row[c]), font, _WIDTHS[i] - 2 * _PAD, rtl) for i, c in enumerate(COLUMNS)]
        height = max(len(c) for c in cells) * _LEAD + _PAD
        if y - height < bottom:
            y = new_page()
        for i, lines in enumerate(cells):
            for n, line in enumerate(lines):
                draw(line, i, y - _SIZE - n * _LEAD)
        y -= height
        pdf.setStrokeGray(0.85)
        pdf.setLineWidth(0.3)
        pdf.line(_MARGIN, y + 1, page_w - _MARGIN, y + 1)
        pdf.setStrokeGray(0)
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
