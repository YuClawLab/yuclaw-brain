# Gate #15 comprehension study — PARTICIPANT SCRIPT (candidate protocol, UNADOPTED; contains no answers)

You are helping test whether YUCLAW's public materials can be understood by a reader who did not build them. This is a test of the materials, not of you. Work alone. Each task has a 10-minute limit; write your answer in the answer sheet before moving on. If you cannot finish a task, write "not completed" and continue. Reading the supplied `VERIFY.md` is allowed at any time; asking a person for help is not (if it happens, say so on the sheet).

You received: the README file, a verification packet directory, local copies of the site pages `index.html` and `evidence_scoreboard.html` (with `receipts/scoreboard.json` and `capabilities.json`), and — in EXECUTION mode only — a computer with the `yuclaw` command installed from the supplied wheel file. Your session mode (EXECUTION or TRANSCRIPT) is written on your answer sheet.

## Task 1 — Check (both modes)
Open `README.md` and find the recorded CLI transcript block. Locate the recorded output of:

    yuclaw check-claim --text "NVDA reported an insider sale in May 2026"

Question: **What does this recorded output establish, and what does it not establish?** Write 2–5 sentences.

## Task 2 — Reproduce
EXECUTION mode: in a terminal, run

    yuclaw packet verify <the packet directory you were given>

and read its output. TRANSCRIPT mode: read the recorded output of that command printed at the end of the packet's `VERIFY.md`.

Question: **What did the verification check, what did it reproduce, and what does a SUCCESS result not establish?** Write 2–5 sentences.

## Task 3 — Read the scoreboard (both modes)
Open `evidence_scoreboard.html`.

Question: **How many outsider reproductions of the exact wheel you were given (or, in TRANSCRIPT mode, of the exact 7.0.0 wheel named in the packet's manifest) does the scoreboard show as verified? Is that number a zero, a pending/unavailable state, or hidden? Does the "legacy program entries" figure count towards it?** Write 2–4 sentences.

## Task 4 — Limits (both modes)
Open `index.html` and the disclaimer box on `evidence_scoreboard.html`.

Question: **Does any page tell you whether to buy or sell anything, or what a strategy will return? What does the disclaimer say the evidence is for?** Write 2–4 sentences.

## Task 5 — Challenge
EXECUTION mode: record one challenge about anything you believe is wrong or unclear in the materials, using this command (replace the three bracketed values; the sha256 and size of the bundle are printed in the packet's `PACKET_MANIFEST.json` under `docs/replay/lab_replay_bundle.json`):

    yuclaw challenge --store ~/yuclaw-study-store --synthetic create study-[your session code]-1 \
      --artifact-type bundle --sha256 [bundle sha256 from PACKET_MANIFEST.json] --size-bytes [bundle size_bytes] \
      --claim-id study-claim-1 --expected "[what you expected to see]" --observed "[what you actually saw]"

Then run `yuclaw challenge --store ~/yuclaw-study-store --synthetic list` and copy the printed `disposition` and `adverse` values onto your sheet.

TRANSCRIPT mode: fill in the challenge template printed in `VERIFY.md` (the same fields: artifact type, sha256, size, claim id, expected, observed) on your answer sheet.

Question: **What did recording the challenge change about the published evidence?** Write 1–3 sentences. (For your information: the challenge you recorded is a local record in your own study store; the public scoreboard shows only challenges that were imported and, later, their dispositions by a designated reviewer; the disposition history is kept and the original finding is never erased.)

Please do not open the `docs/methodology` folder of the website or repository during the session (it contains the reviewer's scoring key); tell the reviewer if you did.

Thank you. Hand in the answer sheet. Your session code is the only identifier on it.
