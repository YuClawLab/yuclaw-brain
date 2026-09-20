"""The four v8 modules built into the workbench (V8-014): SHD, EVO, COM and PRC.

  SHD  Distillation Shield        a deterministic boundary around untrusted evidence bundles: an owner-controlled approval
                                  registry, a restricted worker, typed results. It trains nothing and proves no statement true.
  EVO  Evolution Evidence Audit   measured / declared / unknown inventory of an AI system's parts, and which review evidence
                                  still applies after a change. It audits; it controls no deployment.
  COM  Research Commons Guard     a durable, duplicate-aware review queue with authenticated admission and transactional budgets.
  PRC  Independent Practice       an attempt-before-comparison session with server-held comparisons and preserved attempts.

One identity universe: every module names the workbench's own claim, claim-version and source identifiers. One journal:
module events are additive kinds in the workspace log. One local authorization boundary: v8/workbench/modules/authz.py.
Research and education only. Not investment advice."""

STATUS_WORDS = ("IMPLEMENTED", "INSTALLED_AND_DEMONSTRATED", "HOSTED_CI_VERIFIED", "RELEASED")   # never collapsed into one completion word
