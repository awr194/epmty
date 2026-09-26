from market.nace_sam import _dedupe_prefixes, count_active_by_nace, sam_for_nace

HEADER = "ICO,OKRESLAU,DDATVZN,DDATZAN,ZPZAN,DDATPAKT,FORMA,ROSFORMA,KATPO,NACE,NACE2025,ICZUJ,FIRMA,CISS2010,KODADM,TEXTADR,PSC,OBEC_TEXT,COBCE_TEXT,ULICE_TEXT,TYPCDOM,CDOM,COR,DATPLAT,PRIZNAK"


def _row(ico, nace, forma="112", katpo="120", ended=""):
    return f'{ico},CZ0100,2020-01-01,{ended},,2026-01-15,{forma},{forma},{katpo},{nace},{nace},500054,"Firma",11002,1,"",11000,Praha,Praha,Ulice,1,1,,2026-09-15,'


def _csv(tmp_path, rows):
    p = tmp_path / "res.csv"
    p.write_text("\n".join([HEADER, *rows]) + "\n", encoding="utf-8")
    return p


def test_counts_only_active_subjects_by_prefix(tmp_path):
    p = _csv(tmp_path, [
        _row("1", "56100"),                          # restaurant s.r.o. with employees
        _row("2", "56100", forma="101", katpo="110"),  # OSVČ restaurant, no employees
        _row("3", "5630", forma="101", katpo="000"),  # bar, employees not stated
        _row("4", "56100", ended="2024-05-01"),      # terminated -> ignored
        _row("5", "", forma="101"),                  # no NACE -> ignored
    ])
    counts, as_of = count_active_by_nace(p)
    assert as_of == "2026-09-15"
    assert counts["56"] == {"total": 3, "natural_persons": 2, "legal_entities": 1, "with_employees": 1}
    assert counts["5610"]["total"] == 2 and counts["56100"]["total"] == 2
    assert counts["5630"]["total"] == 1
    assert "561000" not in counts


def test_sam_for_nace_dedupes_overlapping_prefixes():
    cache = {"counts": {"56": {"total": 10, "natural_persons": 6, "legal_entities": 4, "with_employees": 3},
                        "5610": {"total": 7, "natural_persons": 4, "legal_entities": 3, "with_employees": 2},
                        "9602": {"total": 5, "natural_persons": 5, "legal_entities": 0, "with_employees": 1}}}
    assert sam_for_nace(["56", "5610"], cache=cache) == 10  # 5610 is inside 56
    assert sam_for_nace(["5610", "9602"], "with_employees", cache=cache) == 3
    assert sam_for_nace(["9999"], cache=cache) == 0


def test_sam_for_nace_without_data_returns_none():
    assert sam_for_nace(["56"], cache={}) is None
    assert sam_for_nace([], cache={"counts": {"56": {"total": 1}}}) is None


def test_dedupe_prefixes():
    assert _dedupe_prefixes(["5610", "56", "9602", "960"]) == ["56", "960"]
