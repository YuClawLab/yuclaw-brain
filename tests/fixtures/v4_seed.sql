-- v4 CI seed fixture (Day 10): minimal, SYNTHETIC data so the REST signal endpoints
-- return real 'ok' responses in CI (not just no_data). Covers AMD, NVDA, ABT at
-- as_of 2026-05-20. signal_snapshots carry component_anatomy so build_response uses
-- the persisted path (no compose_at market recompute needed in CI).
-- Idempotent-ish: ON CONFLICT DO NOTHING.

-- ── signal_snapshots ────────────────────────────────────────────────────────
INSERT INTO signal_snapshots
  (snapshot_id, ticker, signal_time, available_as_of, signal_label, total_score,
   c1_price_momentum, c2_volume_confirm, c3_sector_velocity, c4_macro_regime,
   c5_oil_rates_fx, c6_event_impact, c7_peer_correlation, c8_cascade_effect, c9_model_trust,
   evidence_event_ids, content_hash, compliance_payload, is_backfill,
   component_anatomy, composite_confidence)
VALUES
  ('seed_AMD_20260520', 'AMD', '2026-05-20T12:00:00Z', '2026-05-20T12:00:00Z', 'WATCH', 0.18,
   0.50, 0.10, -0.20, 0.40, -0.30, 0.20, 0.60, 0.05, -0.20,
   ARRAY['SEED_AMD_MA','SEED_AMD_EB'], 'seedhash_amd', '{"not_advice":true}'::jsonb, false,
   '{"c1":{"score":0.5,"confidence":0.6,"rationale":"momentum positive","evidence_ids":[],"not_implemented":false},
     "c2":{"score":0.1,"confidence":0.3,"rationale":"volume","evidence_ids":[],"not_implemented":true},
     "c3":{"score":-0.2,"confidence":0.5,"rationale":"sector","evidence_ids":[],"not_implemented":false},
     "c4":{"score":0.4,"confidence":0.6,"rationale":"macro RISK_ON","evidence_ids":[],"not_implemented":false},
     "c5":{"score":-0.3,"confidence":0.4,"rationale":"rates","evidence_ids":[],"not_implemented":false},
     "c6":{"score":0.2,"confidence":0.7,"rationale":"events","evidence_ids":["SEED_AMD_MA"],"not_implemented":false},
     "c7":{"score":0.6,"confidence":0.6,"rationale":"peers","evidence_ids":[],"not_implemented":false},
     "c8":{"score":0.05,"confidence":0.3,"rationale":"cascade","evidence_ids":[],"not_implemented":false},
     "c9":{"score":-0.2,"confidence":0.5,"rationale":"model trust","evidence_ids":[],"not_implemented":false}}'::jsonb,
   0.55),
  ('seed_NVDA_20260520', 'NVDA', '2026-05-20T12:00:00Z', '2026-05-20T12:00:00Z', 'NEUTRAL', 0.28,
   0.60, 0.20, -0.10, 0.40, -0.20, 0.10, 0.70, 0.00, -0.10,
   ARRAY['SEED_NVDA_GR'], 'seedhash_nvda', '{"not_advice":true}'::jsonb, false,
   '{"c1":{"score":0.6,"confidence":0.6,"rationale":"momentum","evidence_ids":[],"not_implemented":false},
     "c2":{"score":0.2,"confidence":0.3,"rationale":"volume","evidence_ids":[],"not_implemented":true},
     "c3":{"score":-0.1,"confidence":0.5,"rationale":"sector","evidence_ids":[],"not_implemented":false},
     "c4":{"score":0.4,"confidence":0.6,"rationale":"macro","evidence_ids":[],"not_implemented":false},
     "c5":{"score":-0.2,"confidence":0.4,"rationale":"rates","evidence_ids":[],"not_implemented":false},
     "c6":{"score":0.1,"confidence":0.7,"rationale":"events","evidence_ids":["SEED_NVDA_GR"],"not_implemented":false},
     "c7":{"score":0.7,"confidence":0.6,"rationale":"peers","evidence_ids":[],"not_implemented":false},
     "c8":{"score":0.0,"confidence":0.3,"rationale":"cascade","evidence_ids":[],"not_implemented":false},
     "c9":{"score":-0.1,"confidence":0.5,"rationale":"trust","evidence_ids":[],"not_implemented":false}}'::jsonb,
   0.54),
  ('seed_ABT_20260520', 'ABT', '2026-05-20T12:00:00Z', '2026-05-20T12:00:00Z', 'NEUTRAL', 0.22,
   0.05, 0.05, 0.03, 0.40, -0.10, 0.30, 0.10, 0.00, 0.00,
   ARRAY['SEED_ABT_EB'], 'seedhash_abt', '{"not_advice":true}'::jsonb, false,
   '{"c1":{"score":0.05,"confidence":0.2,"rationale":"momentum","evidence_ids":[],"not_implemented":false},
     "c2":{"score":0.05,"confidence":0.2,"rationale":"volume","evidence_ids":[],"not_implemented":true},
     "c3":{"score":0.03,"confidence":0.4,"rationale":"sector","evidence_ids":[],"not_implemented":false},
     "c4":{"score":0.4,"confidence":0.6,"rationale":"macro","evidence_ids":[],"not_implemented":false},
     "c5":{"score":-0.1,"confidence":0.4,"rationale":"rates","evidence_ids":[],"not_implemented":false},
     "c6":{"score":0.3,"confidence":0.8,"rationale":"earnings beat","evidence_ids":["SEED_ABT_EB"],"not_implemented":false},
     "c7":{"score":0.1,"confidence":0.4,"rationale":"peers","evidence_ids":[],"not_implemented":false},
     "c8":{"score":0.0,"confidence":0.3,"rationale":"cascade","evidence_ids":[],"not_implemented":false},
     "c9":{"score":0.0,"confidence":0.4,"rationale":"trust","evidence_ids":[],"not_implemented":false}}'::jsonb,
   0.28)
ON CONFLICT (snapshot_id) DO NOTHING;

-- ── events (~10 accepted source events) ─────────────────────────────────────
INSERT INTO events
  (event_id, ticker, event_type, magnitude, direction, event_time, source_publish_time,
   source_ingested_time, available_as_of, source_type, source_url, raw_excerpt,
   llm_model, llm_confidence, llm_reasoning, content_hash, prompt_version, event_status,
   parent_event_id, cascade_depth)
VALUES
  ('SEED_AMD_MA','AMD','M_AND_A_ANNOUNCE',0.6,1,'2026-05-15T12:00:00Z','2026-05-15T12:00:00Z','2026-05-15T12:00:00Z','2026-05-15T12:00:00Z','8-K','https://www.sec.gov/Archives/edgar/data/2488/000119312526226746/d118163d8k.htm','AMD announced an acquisition.','yuclaw-llm-70b',0.9,'','seed_e1','v2','accepted',NULL,0),
  ('SEED_AMD_EB','AMD','EARNINGS_BEAT',0.5,1,'2026-05-05T12:00:00Z','2026-05-05T12:00:00Z','2026-05-05T12:00:00Z','2026-05-05T12:00:00Z','8-K','https://www.sec.gov/Archives/edgar/data/2488/000000248826000072/amd-20260505.htm','AMD reported Q1 results.','yuclaw-llm-70b',0.85,'','seed_e2','v2','accepted',NULL,0),
  ('SEED_AMD_OM','AMD','OTHER_MATERIAL',0.3,0,'2026-05-10T12:00:00Z','2026-05-10T12:00:00Z','2026-05-10T12:00:00Z','2026-05-10T12:00:00Z','8-K','https://www.sec.gov/Archives/edgar/data/2488/seed3/x.htm','Material event.','yuclaw-llm-70b',0.7,'','seed_e3','v2','accepted',NULL,0),
  ('SEED_NVDA_GR','NVDA','GUIDANCE_RAISE',0.7,1,'2026-05-18T12:00:00Z','2026-05-18T12:00:00Z','2026-05-18T12:00:00Z','2026-05-18T12:00:00Z','8-K','https://www.sec.gov/Archives/edgar/data/1045810/seed/x.htm','NVDA raised guidance.','yuclaw-llm-70b',0.9,'','seed_e4','v2','accepted',NULL,0),
  ('SEED_NVDA_EC','NVDA','EXEC_CHANGE',0.4,0,'2026-05-08T12:00:00Z','2026-05-08T12:00:00Z','2026-05-08T12:00:00Z','2026-05-08T12:00:00Z','8-K','https://www.sec.gov/Archives/edgar/data/1045810/seed2/x.htm','Board appointment.','yuclaw-llm-70b',0.8,'','seed_e5','v2','accepted',NULL,0),
  ('SEED_NVDA_OM','NVDA','OTHER_MATERIAL',0.3,0,'2026-04-25T12:00:00Z','2026-04-25T12:00:00Z','2026-04-25T12:00:00Z','2026-04-25T12:00:00Z','8-K','https://www.sec.gov/Archives/edgar/data/1045810/seed3/x.htm','Press release.','yuclaw-llm-70b',0.75,'','seed_e6','v2','accepted',NULL,0),
  ('SEED_ABT_EB','ABT','EARNINGS_BEAT',0.6,1,'2026-04-16T12:00:00Z','2026-04-16T12:00:00Z','2026-04-16T12:00:00Z','2026-04-16T12:00:00Z','8-K','https://www.sec.gov/Archives/edgar/data/1800/seed/x.htm','Abbott Q1 results.','yuclaw-llm-70b',0.85,'','seed_e7','v2','accepted',NULL,0),
  ('SEED_ABT_OM','ABT','OTHER_MATERIAL',0.2,0,'2026-04-20T12:00:00Z','2026-04-20T12:00:00Z','2026-04-20T12:00:00Z','2026-04-20T12:00:00Z','8-K','https://www.sec.gov/Archives/edgar/data/1800/seed2/x.htm','Material event.','yuclaw-llm-70b',0.7,'','seed_e8','v2','accepted',NULL,0),
  ('SEED_AMD_DIV','AMD','DIVIDEND_CHANGE',0.3,1,'2026-05-12T12:00:00Z','2026-05-12T12:00:00Z','2026-05-12T12:00:00Z','2026-05-12T12:00:00Z','8-K','https://www.sec.gov/Archives/edgar/data/2488/seed4/x.htm','Dividend declared.','yuclaw-llm-70b',0.8,'','seed_e9','v2','accepted',NULL,0),
  ('SEED_NVDA_PART','NVDA','PARTNERSHIP',0.4,1,'2026-05-14T12:00:00Z','2026-05-14T12:00:00Z','2026-05-14T12:00:00Z','2026-05-14T12:00:00Z','8-K','https://www.sec.gov/Archives/edgar/data/1045810/seed4/x.htm','Strategic partnership.','yuclaw-llm-70b',0.8,'','seed_e10','v2','accepted',NULL,0)
ON CONFLICT (event_id) DO NOTHING;
