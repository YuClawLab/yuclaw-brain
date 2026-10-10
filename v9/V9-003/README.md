# V9-003 — candidate scorecard and clean-install record (commit b16cc334, tree 941de222)

- `scorecard.json` — pytest's own counts for tests/test_v9_brief_engine.py, test_v9_brief_web.py, test_v9_brief_packaging.py,
  test_release_notes_v9.py: 77/77 on Python 3.12.3 and 77/77 on Python 3.10.21 (the declared minimum); installed self-check
  17/17; browser inspection PASS (V9-001); clean install recorded here.
- `clean_install_packaging.json` — tools/yuclaw_v8_clean_install.py on commit b16cc334 with SOURCE_DATE_EPOCH 1580601600,
  twine 7.0.0 check PASSED, wheel `yuclaw-8.0.1-py3-none-any.whl` sha256 51910b1a7954d6b5… (1,131,888 B), sdist
  `yuclaw-8.0.1.tar.gz` sha256 412cd94ba5b69dc7… (6,275,551 B). From BOTH fresh installs, outside the checkout, with no
  PYTHONPATH: the v8 fixtures journey 7/7, the v8 modules journey 6/6, the v8 selftest in both entry forms, the v9 self-check
  17/17 in both entry forms (`yuclaw workbench brief selftest`, `python -m v9.brief selftest`) with the v9 module inside the
  venv, and the installed v9 journey example → export → verify SUCCESS in a fresh workspace with a one-byte-tampered
  packet refused (exit 3).
- The record's overall result is FAIL because of ONE check, `readme_transcript_exact`: the README's `yuclaw replay-lab`
  transcript (frozen for 8.0.1 on 2026-09-21) no longer matches the replay bundle, which the nightly page refresh rewrites
  on main (last on 2026-10-09). This drift exists on origin/main independently of v9 and is regenerated as a freeze-day
  step of the established release process; it is not hidden here and not patched around. Every other check passes.
- These are CANDIDATE artifacts built with the 8.0.1 version string (the version bump is a freeze-day step); they are not
  published, tagged or uploaded anywhere.
