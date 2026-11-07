"""T070 - R6-A1, R6-A4, SC-005: PDF and XLSX carry the same rows and columns; fingerprint in the footer; Arabic and French,
RTL, embedded fonts. No network, no database."""
import datetime as dt
import io
import re
import uuid

import pytest

COLUMNS = ("date", "parcel", "crop", "product", "active_ingredient", "dose", "area_ha", "operator", "warnings", "unchecked", "corrected")
META = {"farm_name": "Ferme Atlas", "period_from": dt.date(2026, 1, 1), "period_to": dt.date(2026, 12, 31),
        "generated_at": dt.datetime(2026, 11, 7, 9, 30, tzinfo=dt.UTC), "catalog_version": "2026-10-01"}


def entry(**kw):
    base = dict(id=uuid.uuid4(), performed_on=dt.date(2026, 3, 4), parcel_name="Oliviers du bas", crop_name="Olivier",
                product_name="Cuprex 50", active_ingredients=[{"name": "cuivre", "concentration": "50%"}], dose=2, dose_unit="L/ha",
                area_ha=1.5, operator_name="Karim", warnings=[], is_free_product=False, corrected=False)
    base.update(kw)
    return base


def rows(lang="fr", n=3, **kw):
    from app.operations import export_job

    return [export_job.entry_to_row(entry(performed_on=dt.date(2026, 3, 1 + i), **kw), lang) for i in range(n)]


def pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    return "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(data)).pages)


def sheet(data: bytes):
    from openpyxl import load_workbook

    return load_workbook(io.BytesIO(data)).active


def test_given_the_export_then_the_required_columns_are_exposed_in_a_fixed_order_with_labels_in_every_language():
    from app.operations import export_job

    assert tuple(export_job.COLUMNS) == COLUMNS
    for lang in ("fr", "ar", "ary"):
        assert tuple(export_job.LABELS[lang]) == COLUMNS and all(export_job.LABELS[lang].values())


def test_given_the_same_rows_when_exporting_to_xlsx_then_the_header_and_every_row_use_the_same_columns():
    from app.operations import export_job

    data = export_job.render_xlsx(rows(n=3), lang="fr", meta=META)
    ws = sheet(data)
    values = [[c.value for c in r] for r in ws.iter_rows(min_row=1, max_row=4)]
    assert values[0] == [export_job.LABELS["fr"][c] for c in COLUMNS]
    assert len(values) == 4 and all(len(v) == len(COLUMNS) for v in values)
    assert values[1][1] == "Oliviers du bas" and values[1][3] == "Cuprex 50" and values[1][4].startswith("cuivre")
    assert "L/ha" in str(values[1][5]) and values[1][7] == "Karim"


def test_given_the_same_rows_when_exporting_to_pdf_and_xlsx_then_both_show_the_same_columns_and_values():
    from app.operations import export_job

    data = rows(n=2)
    text = pdf_text(export_job.render_pdf(data, lang="fr", meta=META))
    for label in export_job.LABELS["fr"].values():
        assert label in text
    for row in data:
        for col in ("parcel", "product", "operator"):
            assert str(row[col]) in text


def test_given_a_treatment_with_a_warning_when_exporting_then_the_localised_warning_appears_in_both_files(monkeypatch):
    from app.operations import export_job

    r = [export_job.entry_to_row(entry(warnings=[{"code": "dose_above_max", "severity": "warning"}, {"code": "dar_unknown", "severity": "warning"}]), "fr")]
    label = export_job.WARNING_LABELS["fr"]["dose_above_max"]
    assert label in sheet(export_job.render_xlsx(r, lang="fr", meta=META)).cell(2, COLUMNS.index("warnings") + 1).value
    assert label in pdf_text(export_job.render_pdf(r, lang="fr", meta=META)).replace("\n", " ")
    assert "dose_above_max" not in str(r[0]["warnings"])


def test_given_every_warning_code_then_a_label_exists_in_each_language():
    from app.domain.phyto_controls import WARNING_CODES
    from app.operations import export_job

    for lang in ("fr", "ar", "ary"):
        assert set(export_job.WARNING_LABELS[lang]) >= set(WARNING_CODES)


def test_given_a_free_product_and_a_corrected_entry_when_exporting_then_they_are_flagged_unchecked_and_corrected():
    from app.operations import export_job

    yes, no = export_job.YES_NO["fr"]
    free = export_job.entry_to_row(entry(is_free_product=True, product_name="Maison"), "fr")
    fixed = export_job.entry_to_row(entry(corrected=True), "fr")
    plain = export_job.entry_to_row(entry(), "fr")
    assert (free["unchecked"], free["corrected"]) == (yes, no)
    assert (fixed["unchecked"], fixed["corrected"]) == (no, yes)
    assert (plain["unchecked"], plain["corrected"]) == (no, no)


def test_given_rows_when_fingerprinting_then_the_sha256_is_stable_and_changes_with_any_value():
    from app.operations import export_job

    a = rows(n=3)
    assert re.fullmatch(r"[0-9a-f]{64}", export_job.content_sha256(a)) and export_job.content_sha256(a) == export_job.content_sha256([dict(r) for r in a])
    b = [dict(r) for r in a]
    b[1]["dose"] = "9 L/ha"
    assert export_job.content_sha256(b) != export_job.content_sha256(a)
    assert export_job.content_sha256(a[:2]) != export_job.content_sha256(a)


def test_given_an_export_when_reading_the_footer_then_farm_period_date_catalogue_version_and_the_same_sha256_are_printed():
    from app.operations import export_job

    data = rows(n=3)
    digest = export_job.content_sha256(data)
    text = pdf_text(export_job.render_pdf(data, lang="fr", meta=META)).replace("\n", "")
    for token in ("Ferme Atlas", "2026-01-01", "2026-12-31", "2026-11-07", "2026-10-01", digest):
        assert token in text.replace(" ", "") or token in text, token
    footer = sheet(export_job.render_xlsx(data, lang="fr", meta=META)).oddFooter.center.text or ""
    assert digest in footer and "Ferme Atlas" in footer


def test_given_arabic_when_exporting_then_the_text_is_reshaped_the_sheet_is_right_to_left_and_the_font_is_embedded():
    from app.operations import export_job

    for lang in ("ar", "ary"):
        assert export_job.is_rtl(lang) is True
    assert export_job.is_rtl("fr") is False
    word = "الزيتون"
    shaped = export_job.shape_arabic(word)
    assert shaped != word and any(0xFB50 <= ord(ch) <= 0xFEFF for ch in shaped)
    data = rows("ar", n=2, parcel_name=word, operator_name="كريم")
    assert sheet(export_job.render_xlsx(data, lang="ar", meta=META)).sheet_view.rightToLeft is True
    assert sheet(export_job.render_xlsx(rows(), lang="fr", meta=META)).sheet_view.rightToLeft in (False, None)
    pdf = export_job.render_pdf(data, lang="ar", meta=META)
    assert pdf.startswith(b"%PDF") and b"/FontFile2" in pdf and b"/Helvetica" not in pdf


def test_given_french_and_arabic_then_the_embedded_fonts_exist_in_the_repository():
    import pathlib

    from app.operations import export_job

    for lang in ("fr", "ar"):
        path = pathlib.Path(export_job.font_path(lang))
        assert path.is_file() and path.suffix == ".ttf" and path.stat().st_size > 10_000
    assert "Arabic" in pathlib.Path(export_job.font_path("ar")).name


@pytest.mark.parametrize("danger", ["=HYPERLINK(\"http://x\",\"y\")", "+1+1", "-1+1", "@SUM(1)"])
def test_given_a_cell_that_looks_like_a_formula_when_exporting_to_xlsx_then_it_is_stored_as_text(danger):
    from app.operations import export_job

    data = [export_job.entry_to_row(entry(product_name=danger, operator_name=danger), "fr")]
    ws = sheet(export_job.render_xlsx(data, lang="fr", meta=META))
    for col in ("product", "operator"):
        cell = ws.cell(2, COLUMNS.index(col) + 1)
        assert cell.data_type != "f" and not str(cell.value).startswith(("=", "+", "-", "@"))


def test_given_more_rows_than_the_cap_when_rendering_then_it_refuses_before_any_work():
    from app.operations import export_job

    assert export_job.MAX_ROWS == 10_000

    class Huge(list):
        def __len__(self):
            return 10_001

        def __iter__(self):
            raise AssertionError("rows were read before the cap check")

    for render in (export_job.render_xlsx, export_job.render_pdf):
        with pytest.raises(ValueError):
            render(Huge(), lang="fr", meta=META)


def test_given_a_job_then_the_object_keys_are_generated_by_the_server_in_the_documented_shape():
    from app.operations import export_job

    farm, job = uuid.uuid4(), uuid.uuid4()
    keys = {fmt: export_job.export_key(farm, job, fmt) for fmt in ("pdf", "xlsx")}
    for fmt, key in keys.items():
        assert re.fullmatch(r"farms/[0-9a-f-]{36}/exports/[0-9a-f-]{36}/[A-Za-z0-9._-]+", key)
        assert key.startswith(f"farms/{farm}/exports/{job}/") and key.endswith("." + fmt)
    assert export_job.export_key(farm, job, "pdf") == keys["pdf"]  # deterministic per job, never client input
