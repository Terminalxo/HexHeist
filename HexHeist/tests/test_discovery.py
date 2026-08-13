from hexheist.core.discovery import parse_listing


def test_parse_current_style_listing():
    text = """
    avrdude: Version 8.2
      m328p = ATmega328P (SPM, ISP, HVPP, debugWIRE)
      t85    = ATtiny85 (SPM, ISP, HVSP, debugWIRE)
    """
    entries = parse_listing(text)
    ids = {entry.id for entry in entries}
    assert ids == {"m328p", "t85"}


def test_parse_programmers():
    text = """
    Valid programmers are:
      usbasp   = USBasp, http://www.fischl.de/usbasp/
      arduino  = Arduino
    """
    entries = parse_listing(text)
    by_id = {entry.id: entry.description for entry in entries}
    assert "usbasp" in by_id
    assert "USBasp" in by_id["usbasp"]
    assert "arduino" in by_id


def test_parser_ignores_noise():
    text = """
    AVRDUDE 8.2
    avrdude: error: something
    Use -p ? to list parts
    """
    assert parse_listing(text) == []


def test_discover_from_fake_avrdude(tmp_path):
    import os
    from hexheist.core.discovery import discover_parts, discover_programmers, probe_version

    fake = tmp_path / "avrdude"
    fake.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = \"--version\" ]; then echo 'avrdude version 8.2'; exit 0; fi\n"
        "if [ \"$1\" = \"-p\" ]; then echo 'm328p = ATmega328P (ISP)'; exit 0; fi\n"
        "if [ \"$1\" = \"-c\" ]; then echo 'usbasp = USBasp'; exit 0; fi\n"
    )
    fake.chmod(0o755)
    assert probe_version(str(fake)) == "8.2"
    assert [x.id for x in discover_parts(str(fake))] == ["m328p"]
    assert [x.id for x in discover_programmers(str(fake))] == ["usbasp"]
