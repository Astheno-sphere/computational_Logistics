import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from kb_sync import classify, decide

MIT = "MIT License\n\nPermission is hereby granted, free of charge, to any person obtaining a copy"
BSD3 = "Redistribution and use in source and binary forms, with or without modification ... Neither the name of X"
BSD2 = "Redistribution and use in source and binary forms, with or without modification, are permitted"


def test_permissive():
    assert classify(MIT) == "MIT"
    assert classify("Apache License\nVersion 2.0, January 2004") == "Apache-2.0"
    assert classify(BSD3) == "BSD-3-Clause" and classify(BSD2) == "BSD-2-Clause"


def test_copyleft_never_vendored():
    for text, spdx in [("GNU GENERAL PUBLIC LICENSE Version 3", "GPL"),
                       ("GNU LESSER GENERAL PUBLIC LICENSE", "LGPL"),
                       ("GNU AFFERO GENERAL PUBLIC LICENSE", "AGPL"),
                       ("Eclipse Public License - v 2.0", "EPL"),
                       ("Attribution-NonCommercial 4.0", "CC-BY-NC/ND")]:
        assert classify(text) == spdx
        assert decide(spdx, {})[0] == "link-only"


def test_title_wins_over_cross_references():
    gpl3 = "GNU GENERAL PUBLIC LICENSE Version 3 ... see the GNU Affero General Public License"
    lgpl3 = "GNU LESSER GENERAL PUBLIC LICENSE Version 3 ... the GNU General Public License"
    assert classify(gpl3) == "GPL" and classify(lgpl3) == "LGPL"


def test_unknown_and_none_are_link_only():
    assert decide("UNKNOWN", {})[0] == "link-only"
    assert decide("NONE", {})[0] == "link-only"
    assert decide("MIXED:GPL+MIT", {})[0] == "link-only"


def test_sharealike_needs_opt_in():
    assert decide("CC-BY-SA-4.0", {})[0] == "link-only"
    assert decide("CC-BY-SA-4.0", {"allow_sharealike": True})[0] == "vendored"
