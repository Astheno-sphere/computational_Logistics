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


def test_open_copyleft_is_vendored_but_flagged():
    from kb_sync import is_copyleft
    for text, spdx in [("GNU GENERAL PUBLIC LICENSE Version 3", "GPL"),
                       ("GNU LESSER GENERAL PUBLIC LICENSE", "LGPL"),
                       ("GNU AFFERO GENERAL PUBLIC LICENSE", "AGPL"),
                       ("Eclipse Public License - v 2.0", "EPL")]:
        assert classify(text) == spdx
        assert decide(spdx, {})[0] == "vendored" and is_copyleft(spdx)
    assert not is_copyleft("MIT") and is_copyleft("MIXED:GPL+MIT")


def test_not_open_source_is_link_only():
    assert classify("Attribution-NonCommercial 4.0") == "CC-BY-NC/ND"
    for spdx in ("CC-BY-NC/ND", "UNKNOWN", "NONE", "MIXED:GPL+UNKNOWN"):
        assert decide(spdx, {})[0] == "link-only"


def test_title_wins_over_cross_references():
    gpl3 = "GNU GENERAL PUBLIC LICENSE Version 3 ... see the GNU Affero General Public License"
    lgpl3 = "GNU LESSER GENERAL PUBLIC LICENSE Version 3 ... the GNU General Public License"
    assert classify(gpl3) == "GPL" and classify(lgpl3) == "LGPL"
