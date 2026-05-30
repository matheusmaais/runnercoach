# Running Coach — Adaptive Coaching & Safety Hardening Spec

- Status: FINAL (after 3 review passes — see Appendix A)
- Repo state at authoring: `d6f1278 feat: close frontend coaching loop`
- Author role: reviewer/architect (Claude). Implementer: Codex.
- Scope: backend coaching engine (`src/running_coach/`). No frontend changes here.

---

## 0. How to use this document

Implementation contract for Codex. Each finding has:
**severity · root cause · evidence (file:symbol) · correction direction · DoD with a testable invariant.**

Rules for implementation:

- Implement only what satisfies the DoD. No speculative abstraction.
- Default in uncertainty is always the most conservative branch (fail-closed). Never add a path that yields `maintain`/escalation by omission.
- Every new decision rule cites either an approved `science_ref_id` from `data/knowledge/science_refs.yaml` OR a `rule_ref` (coaching heuristic). It must NOT attribute a heuristic to a science ref that does not support it (see C3 / Finding S12).
- Each closed finding ships its DoD test in the same PR. The test is the acceptance.
- Preserve existing green tests for the guardrail envelope and Matheus-only contract — they are safety invariants.
- All thresholds are named module constants (auditable, testable). Values below are the agreed P0 calibration; changing them requires updating the boundary tests.

---

## 1. Consolidated context

### 1.1 What already works — protect with tests, do not regress

- **Deterministic envelope binds the LLM.** `llm.py::validate_llm_response` recomputes the guardrail and rejects LLM actions outside the allowed envelope (`llm.py::_action_allowed_by_guardrail`). Covered by `tests/test_llm.py::test_validate_llm_response_rejects_action_against_high_pse_and_achilles_guardrail`.
- **Matheus-only contract.** Garmin HR/cadence/power/dynamics are Matheus-only; `missing_evidence` flags absent Bruna HR. Bruna uses shared pace + manual PSE/symptoms/sleep/HR-when-present.
- **Red-flag fail-closed.** Explicit red-flag symptom → `replace_with_off`, `blocked_by_red_flag=True`, high confidence.
- **History persists across runs.** `pipeline.py::_merge_with_existing_processed_activities` merges new Garmin rows with `data/processed/activities.csv`. But note Finding ARCH-7 below: merged rows are *raw activities*, not enriched workouts.

### 1.2 The core gap — the product is not adaptive yet

Verified facts (repo `d6f1278`):

- `pipeline.py:171` — `recommendations = {w.workout_id: _recommendation_for_workout(repo_root, w) for w in workouts}`. Each workout scored in isolation.
- `recommendations.py::RecommendationInput` carries only point-in-time fields. No accumulated-load fields.
- `grep deload|consecutive|acwr|rolling|weekly_load` in `recommendations.py` → 0.
- `weekly_summary`/`_trends` live only in `frontend_data.py` (visual); never feed the decision.
- `data/plan/planned_workouts.csv` is 2 static rows; the pipeline never rewrites it.

Consequence: feedback from workout 1 does not shape workouts 2, 3, or the week. Achilles trending 1→2→3 across the week is not a trend; consecutive hard sessions don't escalate; a volume jump triggers nothing. The IOC load ref and the Silbernagel pain-monitoring ref are cited but the accumulation they describe is not implemented — at this point they are decorative.

### 1.3 Two guardrail call-sites (critical architectural constraint — Invariant DIV-1)

The deterministic guardrail is computed in **two** places that must agree:

1. **Pipeline:** `pipeline.py::_recommendation_for_workout` (def at `pipeline.py:486`; builds `RecommendationInput` at `pipeline.py:507`) → `recommend_next_action` → the persisted decision.
2. **LLM enforcement:** `llm.py::_deterministic_guardrail_for_request` (def at `llm.py:351`; builds `RecommendationInput` at `llm.py:367`) → `recommend_next_action`, used in `validate_llm_response` to reject LLM output outside the envelope.

**Invariant DIV-1:** for the same workout + state, the guardrail action used by the LLM enforcement MUST equal the pipeline's recommendation action. Three concrete hazards this spec must close:

- **DIV-1a (recompute hole):** `_deterministic_guardrail_for_request` runs twice — embedded by `build_llm_request` (`llm.py:111`) and again inside `validate_llm_response` (`llm.py:226`). Existing tests mutate `request["latest_shared_workout"][...]` (e.g., `test_llm.py:172`). The accumulated state MUST be carried through identically on both runs; the validation call MUST rebuild `RecommendationInput` from the request's point-in-time fields AND the serialized `accumulated_state` atomically, and MUST NOT re-derive accumulated state from raw history.
- **DIV-1b (history source skew):** the pipeline builds workouts in memory from the *current* Garmin CSV, while `build_llm_request` reads `data/processed/workouts.csv`. If a user exports only recent activities, the in-memory list is shorter than the CSV → divergent accumulated state. Fix in §3.5.
- **DIV-1c (pre-existing all_out_race divergence):** `pipeline.py::_is_all_out_race` matches `category` + `notes`; `llm.py::_is_all_out_race` matches `category` + `next_workout` (a field absent from CSV rows). These already disagree. Must be unified (§3.7).

---

## 2. Findings (severity-ordered)

> DoDs are concretized in §5. This section is the rationale; §3 is the build contract.

- **P0 — Stateless engine (BLOCKER).** Evidence: §1.2. Correction: §3. DoD: §5.1 + §5.2.
- **C1 — Symptom classifier fails open.** `pipeline.py::_classify_symptom_severity` returns `MILD` by default; only `MODERATE` becomes a reason. Correction: unknown non-empty symptom ⇒ at least `MODERATE`; allowlist only for `NONE`; add acute MSK terms to red-flag (explicit list in §3.6). DoD: §5.3.
- **C2 — Achilles: no solo protection; pain-monitoring not implemented.** Evidence: `pipeline.py::_recommendation_for_workout` returns `REQUEST_MANUAL_RESOLUTION` for solo; `ge_3 → DEFER_QUALITY` only. Correction: evaluate Achilles on solo runs; trend rule (§3.4); `ge_3` reduces load. DoD: §5.5.
- **C3 — No load gate (ACWR).** Correction: rolling load gate (§3.4); deload is a **rule-only** heuristic (cite `rule_ref: coaching-principle-deload`, NOT the IOC science ref). DoD: §5.6.
- **A1 — `all_out_race` by string; recovery not multi-day.** Correction: structural flag + multi-day propagation via state. Interim: default `in_post_race_recovery=False` (PSE≥9 pointwise still catches the session). DoD: §5.7.
- **A2 — Bruna paces hardcoded.** Correction: versioned paces with semantics; reject non-race planned pace faster than sustainable. DoD: §5.8.
- **A3 — `gym_previous_day`/lower-body load ignored.** Correction: lower-body load → reduction reason; `could_repeat_last_block=false` → fatigue contribution. DoD: §5.4.
- **A4 — `MAINTAIN ⇒ all actions` lets LLM escalate.** Correction: when guardrail = `maintain`, restrict LLM action set to `{maintain_next_workout, reduce_next_workout, replace_with_easy, replace_with_off, defer_quality}`. DoD: §5.9.
- **M1–M4** — phase-advance gates; sleep escalation; volleyball inference; LLM HR free-text. Deferred after P0/C/A; directions unchanged from prior review.

---

## 3. Technical spec — P0 adaptive engine

### 3.1 Design principle

Introduce a **pure, deterministic** `AccumulatedState` derived from ordered workout history strictly before the workout being decided. The engine consumes point-in-time signals + accumulated state. The identical `AccumulatedState` is serialized into the LLM request so enforcement uses the same inputs (DIV-1).

### 3.2 New types (location: new module `src/running_coach/accumulation.py`)

Rationale for a new module (resolves ARCH-8): `build_athlete_state` is temporal aggregation, a different concern from rule evaluation in `recommendations.py`, and it is imported by both `pipeline.py` and `llm.py`. `RecommendationInput`/`AccumulatedState` stay importable from `recommendations.py` via re-export to keep call-sites simple.

```python
class WorkoutHistoryPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    local_date: date
    distance_km: float | None
    is_running: bool
    bruna_pse: int | None
    matheus_achilles_morning: int | None
    matheus_achilles_after: int | None
    poor_sleep: bool
    all_out_race: bool

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> "WorkoutHistoryPoint": ...
    @classmethod
    def from_workout(cls, w: "WorkoutRecord") -> "WorkoutHistoryPoint": ...
```

`from_csv_row` (resolves ARCH-4) MUST handle: empty string → `None`; `"true"/"false"` → bool; numeric strings → int/float; `local_date` parsed from ISO `YYYY-MM-DD`; `is_running` from `activity_type` casefold == "corrida"; `poor_sleep` via the shared `_is_poor_sleep`; `all_out_race` via the unified detector (§3.7).

```python
class AccumulatedState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Rolling load (resolves ARCH-6/ARCH-10/S7: rolling 7-day windows, NOT ISO weeks)
    last_7d_distance_km: float            # running km in (ref_date - 7, ref_date), excludes decided workout
    prior_28d_mean_7d_distance_km: float  # mean rolling-7d running km over days ref-35..ref-8
    load_ratio: float | None              # last_7d / prior mean; None when insufficient or baseline < MIN_BASELINE_KM
    quality_sessions_last_7d: int         # count of sessions flagged quality/threshold/race in last 7d

    # Fatigue (per-athlete separation, resolves S2)
    bruna_fatigued_week_run: int          # consecutive prior 7d-windows flagged fatigued for Bruna
    matheus_achilles_recent_max: int      # max achilles_after over ACHILLES_LOOKBACK_DAYS, else 0
    matheus_achilles_rising: bool         # see 3.4 (windowed, gap-aware)

    # Race recovery
    days_since_all_out_race: int | None
    in_post_race_recovery: bool

    # Data sufficiency (resolves S8/T6)
    history_days: int
    insufficient_history: bool            # True when fewer than MIN_COMPLETE_WINDOWS rolling windows of data
```

### 3.3 New function: `build_athlete_state`

```python
def build_athlete_state(history: list[WorkoutHistoryPoint], reference_date: date) -> AccumulatedState
```

- Pure, no clock, no I/O. `reference_date` passed in (keeps `build_llm_request` deterministic).
- History = points with `local_date < reference_date`. Same-day disambiguation is done by the **caller** excluding the decided workout by `workout_id` before building points (resolves ARCH-5; avoids any `str`/`date` comparison — points already carry `date` objects).
- `build_athlete_state([], ref)` returns `insufficient_history=True`, `load_ratio=None`, all counters 0, `days_since_all_out_race=None` (resolves T7).

### 3.4 Accumulation rules and constants (calibrated for 3 runs/week, ~20–30 km/week)

```python
RECOVERY_DAYS_BY_EFFORT = {"5k": 4, "10k": 6, "half": 10, "default": 6}  # resolves S4
LOAD_RATIO_CAP = 1.15            # resolves S1: 1.10 fired on benign 30->33km; 1.15 + floor below
LOAD_ABS_FLOOR_KM = 5.0          # spike requires BOTH ratio>cap AND +5km absolute (resolves S1)
MIN_BASELINE_KM = 12.0           # below this trailing baseline, ratio is None (avoids tiny-week noise)
ACHILLES_BLOCK_DELTA = 1         # after-morning >=1 blocks quality (resolves S5)
ACHILLES_REDUCE_DELTA = 2        # after-morning >=2 triggers reduce
ACHILLES_LOOKBACK_DAYS = 28
ACHILLES_TREND_MAX_GAP_DAYS = 7  # rising only if consecutive check-ins within 7d (resolves S10)
FATIGUE_WINDOWS_FOR_DELOAD = 2   # consecutive fatigued 7d-windows -> deload (rule-only)
MIN_COMPLETE_WINDOWS = 3         # < 3 rolling windows of history => insufficient_history
DELOAD_VOLUME_CAP_FRACTION = 0.70
```

**Fatigued 7d-window (Bruna run-load), resolves S2:** flagged when, within the window, **≥2** of: a session with `bruna_pse >= 9` (matches existing hard-stop threshold, not 8); ≥2 poor-sleep nights; a non-easy session count above plan. A single poor night or a single PSE-9 does NOT flag the window. Matheus-Achilles fatigue is tracked separately and never counts toward Bruna's deload counter.

**Reasons emitted (each maps to a ref or rule_ref):**

| Reason tag | Trigger | Effect on envelope | ref |
|---|---|---|---|
| `weekly_load_spike` | `load_ratio is not None and load_ratio > LOAD_RATIO_CAP and (last_7d - prior_mean) > LOAD_ABS_FLOOR_KM` | block escalation; `reduce` if planned harder | `load-management-recovery` |
| `intensity_overreach` | `quality_sessions_last_7d >= 2` (resolves S3: volume-only misses intensity) | block new quality; `defer_quality` | `seiler-intensity-distribution` |
| `consecutive_fatigue_deload` | `bruna_fatigued_week_run >= FATIGUE_WINDOWS_FOR_DELOAD` | `reduce` (deload, see below) | `rule_ref: coaching-principle-deload` |
| `achilles_trend_block` | `(achilles_after-achilles_morning) >= ACHILLES_BLOCK_DELTA` | block quality (`defer_quality`) | `achilles-tendinopathy-load` |
| `achilles_trend_reduce` | rising (gap-aware) OR delta `>= ACHILLES_REDUCE_DELTA` | `reduce`/`off` | `achilles-tendinopathy-load` |
| `post_race_recovery` | `in_post_race_recovery` | `reduce`, no quality | `load-management-recovery` |
| `insufficient_history` | `insufficient_history` | hard cap at `maintain` (no escalation) | `rule_ref: conservative-cold-start` |

**`matheus_achilles_rising`:** True only when the last ≥2 non-null `achilles_after` values within `ACHILLES_LOOKBACK_DAYS` are strictly increasing AND each consecutive pair is within `ACHILLES_TREND_MAX_GAP_DAYS`. Single datapoint or plateau → False. The trend rule is **additive to** the existing pointwise `achilles_ge_3` rule, not a replacement.

**Deload semantics (resolves S6):** a deload = the next recommendation caps action at `reduce` (no quality), conceptually 1 week / 3 sessions at ≤`DELOAD_VOLUME_CAP_FRACTION` of `prior_28d_mean_7d_distance_km`. The counter resets after one window classified as deload regardless of signals during it (prevents infinite loop).

**Precedence (resolves S8, T6 enum gap):** red-flag → pointwise hard stops (PSE≥9, Achilles≥5) → accumulated reasons. Accumulated reasons only **lower** the envelope, never raise it. There is no `INCREASE`/`ADVANCE` value in `RecommendationAction` (`models.py`), so "block escalation" is enforced as: (a) the deterministic action is capped at `maintain`, and (b) the LLM envelope for `maintain` is the tightened set from A4 (§3.6). `insufficient_history` and `weekly_load_spike` therefore manifest as "LLM cannot pick an escalation action and the deterministic action will not exceed the planned easy/maintain."

### 3.5 Wiring (resolves DIV-1a, DIV-1b)

- **Single history source.** BOTH call-sites build history from `data/processed/workouts.csv` (read in the run AFTER the pipeline writes it is not possible within one run, so: the pipeline builds history from its in-memory full workout list **only after** merging full history). To guarantee parity, add `_merge_with_existing_processed_workouts` so the in-memory `workouts` list always equals what `workouts.csv` will contain. The LLM path keeps reading `workouts.csv`. Both then call `WorkoutHistoryPoint.from_*` and `build_athlete_state` with the same `reference_date`. (Resolves ARCH-7.)
- **`RecommendationInput` extension (backward-compatible):** add `accumulated: AccumulatedState | None = None`. When `None`, the engine behaves exactly as today (preserves the 21 `recommendation_input(...)` factory calls in `tests/test_recommendations.py`). Accumulated reasons activate only when provided.
- **`_recommendation_for_workout`** changes signature to receive the full ordered `workouts` plus the target; excludes the target by id; builds points; passes `accumulated`.
- **`_deterministic_guardrail_for_request`** MUST pass `accumulated` built from `request["accumulated_state"]` (read, never re-derived from raw history). `build_llm_request` serializes `accumulated_state` once; `render_llm_request_markdown` renders it for auditability.
- **Mandatory:** the LLM guardrail call MUST pass `accumulated` (not leave it `None`), else accumulated rules silently stop binding the LLM (resolves ARCH-9).

### 3.6 C1 explicit lists and A4 envelope (resolves S9, T4, T10)

- Red-flag additions to `_classify_symptom_severity`: `["fratura","estalo","pop","snap","inchaco agudo","inchaço agudo","nao consegue apoiar","não consegue apoiar","dormencia","dormência","formigamento","luxacao","luxação"]`.
- `NONE` allowlist (only these stay non-reducing): `{"sem sintomas","none","no symptoms","assintomatica","assintomática",""}` and empty list.
- Everything else non-empty ⇒ at least `MODERATE` (fail-closed).
- A4 tightened envelope: `_action_allowed_by_guardrail[MAINTAIN_NEXT_WORKOUT]` changes from `set(RecommendationAction)` to `{maintain_next_workout, reduce_next_workout, replace_with_easy, replace_with_off, defer_quality}`. (Intensity injected via free text `next_workout` is out of scope here; tracked as M4.)

### 3.7 Unified `all_out_race` detector (resolves DIV-1c, S11)

Single function used by both call-sites and by `from_csv_row`. Interim: detect from a structural `category`/explicit flag only; if absent, return `False` (fail-open is acceptable because PSE≥9 pointwise catches the day; multi-day propagation is A1, gated on the schema flag). Remove the `next_workout` key from the LLM-path detector.

### 3.8 Out of scope for P0

- Living plan regeneration of `planned_workouts.csv` (v1.8).
- sRPE / PSE×duration internal load (v1.8). P0 adds the `intensity_overreach` session-count guard as the interim intensity signal.

---

## 4. Implementation order

```
P0  -> AccumulatedState + build_athlete_state + dual-call-site wiring (incl. _merge_with_existing_processed_workouts). Do first.
C1  -> fail-closed symptoms (independent).
A3  -> lower-body load reason (independent).
A4  -> tighten maintain envelope (independent).
C2  -> solo Achilles + trend (uses P0).
C3  -> load gate + deload (uses P0).
A1  -> multi-day recovery + schema flag (uses P0).
A2, M1-M4 -> after.
```

---

## 5. Acceptance — concrete, two-sided, boundary-covered

> Constants referenced below are from §3.4.

### 5.1 P0 adaptation invariant (two-sided; resolves T1, T2)
```
point = recommendation_input(bruna_pse=6, symptom_severity=NONE, matheus_achilles_morning=0,
        matheus_achilles_after=0, volleyball_previous_day=False, poor_sleep=False,
        all_out_race=False, planned_action=MAINTAIN_NEXT_WORKOUT, phase="half_base",
        week_number=5, planned_workout_id="plan-5")
heavy = build_athlete_state(history: last_7d=40km, prior_28d_mean_7d=30km, ...)  # ratio 1.33, +10km
light = build_athlete_state(history: last_7d=15km, prior_28d_mean_7d=30km, ...)  # ratio 0.50
assert recommend_next_action(point.copy(update={accumulated:heavy})).action in {REDUCE_NEXT_WORKOUT, REPLACE_WITH_EASY}
assert "weekly_load_spike" in heavy_result.reasons
assert recommend_next_action(point.copy(update={accumulated:light})).action == MAINTAIN_NEXT_WORKOUT  # MUST maintain
assert "weekly_load_spike" not in light_result.reasons
```

### 5.2 Integration: pipeline actually passes accumulated (resolves T2)
Spy/monkeypatch `recommend_next_action`; run `run_pipeline` on a fixture with ≥5 processed workouts; assert the captured input has `accumulated is not None` and `accumulated.history_days > 0`.

### 5.2b DIV-1 parity (resolves T3, DIV-1)
```
pipeline_result = _recommendation_for_workout(repo_root, latest_workout)   # via spy or return
request = build_llm_request(repo_root)
assert pipeline_result.action.value == request["deterministic_guardrail"]["action"]
assert pipeline_result.reasons == request["deterministic_guardrail"]["reasons"]
# negative: tamper request["accumulated_state"] -> validate uses serialized value, not re-derived
```

### 5.3 C1 fail-closed (canonical fixtures; resolves T4, S9)
```
UNKNOWN = ["dor muscular leve","cansaco nas pernas","desconforto joelho","pontada lateral",
 "rigidez lombar","formigamento pe","inchaco tornozelo","caimbra panturrilha",
 "pressao no quadril","queimacao canela","tensao no ombro","dor no calcanhar"]
for s in UNKNOWN:
    assert _classify_symptom_severity([s]) >= SymptomSeverity.MODERATE
    assert recommend_next_action(recommendation_input(symptom_severity=_classify_symptom_severity([s]))).action != MAINTAIN_NEXT_WORKOUT
assert _classify_symptom_severity(["sem sintomas"]) == NONE
assert _classify_symptom_severity([]) == NONE
# red-flag additions:
for s in ["estalo no tendao","nao consegue apoiar","dormencia no pe"]:
    assert _classify_symptom_severity([s]) == RED_FLAG
# pipeline path (resolves T9): checkin with unknown symptom -> decision action != maintain_next_workout
```

### 5.4 A3 lower-body load
`recommendation_input(lower_body_load_previous_day=True)` ⇒ action == `REDUCE_NEXT_WORKOUT`; `could_repeat_last_block=False` contributes a fatigue reason.

### 5.5 C2 Achilles
Solo run, Achilles 5 ⇒ action != `maintain`. Rising trend `[after=1 @day-6, after=3 @day-3]` within 7d ⇒ `achilles_trend_reduce`. Plateau `[2,2]` ⇒ not rising. Single datapoint ⇒ not rising. Gap > 7d ⇒ not rising. delta==1 ⇒ blocks quality (`defer_quality`), delta>=2 ⇒ reduce.

### 5.6 C3 load + boundaries (resolves T5, T8, T12, S12)
```
# ratio exactly at cap with floor not crossed -> no spike
state(last_7d=13.8, prior=12.0)  # ratio 1.15 exactly, +1.8km < floor -> no weekly_load_spike, action maintain
state(last_7d=18.0, prior=12.0)  # ratio 1.5, +6km > floor -> weekly_load_spike, reduce/easy
# deload counter resets on non-fatigued window
windows [fatigued, fatigued, NOT, fatigued]  (most-recent-first) -> bruna_fatigued_week_run == 1
windows [fatigued, fatigued, fatigued, NOT]                      -> bruna_fatigued_week_run == 3
# consecutive_fatigue_deload cites rule_ref, NOT load-management-recovery
assert "load-management-recovery" not in result.science_refs when only deload fired
```

### 5.7 A1 post-race boundary (resolves T8, S11)
10k effort at day-6 ⇒ `in_post_race_recovery` True (RECOVERY_DAYS_BY_EFFORT["10k"]=6). day-7 ⇒ False. Absent structural flag ⇒ `in_post_race_recovery` False (interim fail-open; PSE≥9 still catches the session).

### 5.8 A2 pace invariant
Non-race planned workout with pace faster than the configured sustainable ceiling is rejected at load time.

### 5.9 A4 envelope (testable reframing; resolves T10)
With guardrail action = `MAINTAIN_NEXT_WORKOUT`, `validate_llm_response` rejects an LLM response whose `next_workout_action` is outside `{maintain_next_workout, reduce_next_workout, replace_with_easy, replace_with_off, defer_quality}` (e.g., `bruna_without_matheus`).

### 5.10 insufficient_history hard cap (resolves S8, T6)
`build_athlete_state([], ref)` ⇒ `insufficient_history True`, `load_ratio None`. With `insufficient_history`, deterministic action is capped at `maintain` and the LLM envelope (A4) forbids escalation actions.

### Definition of done for the set
1. §5.1 (two-sided adaptation) and §5.2b (DIV-1 parity) pass.
2. §5.2 (pipeline wiring spy) passes — feature works end-to-end, not just in unit isolation.
3. §5.3 (C1 fail-closed, incl. pipeline path) passes.
4. All boundary tests (§5.6, §5.7, §5.5) pass; no `>=`/`<` off-by-one.
5. All pre-existing envelope and Matheus-only tests remain green.

When 1–5 hold, the product has moved from a per-workout safety evaluator to a conservative adaptive coach.

---

## Appendix A — Review log (3 passes complete)

Draft v0 reviewed by three specialized passes; all integrated into this FINAL.

- **Pass 1 — Sports-science correctness.** Findings integrated: S1 (WoW 1.10→1.15 + abs floor + min baseline), S2 (fatigued-week PSE 8→9, ≥2 signals, per-athlete split), S3 (added `intensity_overreach` session-count guard; volume-only ACWR no longer claimed to satisfy IOC ref), S4 (RECOVERY_DAYS effort-scaled), S5 (Achilles block@delta1/reduce@delta2, additive to pointwise), S6 (deload defined + counter reset), S7 (window 28→35 / rolling), S8 (insufficient_history hard cap), S9 (explicit red-flag list), S10 (gap-aware rising), S11 (all_out_race interim fail-open), S12 (deload is rule-only, not the IOC science ref).
- **Pass 2 — Architecture/determinism.** Findings integrated: ARCH-1/DIV-1a (validation reads serialized state, never recomputes), ARCH-2 (line numbers corrected to 486/507/351/367), ARCH-3 (test count clarified: 21 `recommendation_input(...)` factory calls; 13 `recommend_next_action` calls), ARCH-4 (`from_csv_row` converter specified), ARCH-5 (same-day exclusion by id; date objects avoid `str<date`), ARCH-6/10/S7 (rolling 7-day windows, not ISO weeks; Monday/Sunday cliff removed), ARCH-7/DIV-1b (`_merge_with_existing_processed_workouts` so both sources match), ARCH-8 (new `accumulation.py` module), ARCH-9 (guardrail MUST pass `accumulated`), ARCH-11/DIV-1c (unify `all_out_race`).
- **Pass 3 — Testability/DoD.** Findings integrated: T1/T2 (two-sided P0 test + pipeline spy), T3 (DIV-1 parity test), T4/S9 (canonical C1 fixtures), T5 (ratio boundary 1.15), T6 (insufficient_history rule + enum-gap reframing; no nonexistent `advance` action asserted), T7 (empty-history behavior), T8 (post-race day-6/7 boundary), T9 (C1 pipeline-path integration assertion), T10 (A4 reframed to action-set), T11 (Achilles window tests), T12 (fatigue counter reset tests).

Residual risk accepted for P0: free-text intensity injection (M4) and string-based race detection (A1 interim) remain until the check-in schema gains a structural race flag. Both are fail-safe given PSE≥9 pointwise enforcement.


---

# v1.8 — Periodization Spine & Event-Driven Planning (DRAFT — pending review)

> Goal of the platform, stated by the athlete: a real coach that (a) keeps the January 2027 half-marathon as the north star and gets progressively more specific toward it, (b) is driven by the real race calendar — 5K/10K races that are NOT known in advance and must be addable anytime, used to benchmark evolution and stay social, and (c) keeps reacting to training feedback + real routine (v1.7). The plan must be re-balanceable on a 4–8 week horizon: some blocks have a race, others do not, and the calendar is unknown today.

## v1.8.0 Design principles

1. **Deterministic spine, LLM skin.** The macrocycle, phase transitions, and where each race sits are decided by versioned data + deterministic rules. The LLM only renders/personalizes the individual session inside the block the engine already placed. The LLM never owns periodization (preserves the safety contract and DIV-1).
2. **Reverse-anchored from the A-race.** Phases are derived backward from `target.date_window` (2027-01-24/31). The plan is not a fixed sheet to January; it is a **rolling 4–8 week horizon** re-derived whenever inputs change.
3. **Event-driven, not calendar-fixed.** Races are first-class events the athlete adds when they learn about them. Adding/removing a race re-derives the affected horizon (mini-taper before, recovery after) WITHOUT mutating past, already-trained workouts.
4. **Append-only history; future is regenerable.** Past workouts and decisions are immutable audit trail. Only future planned workouts are (re)generated.
5. **Races are typed by priority.** A (goal half), B (important tune-up, short taper), C (training/social race, run through with minimal taper). Priority controls taper length and whether the block goal bends.

## v1.8.1 New versioned data

- `data/plan/macrocycle.yaml` — phase ladder with reverse anchoring:
  - ordered phases (e.g., `base → 5_10k_sharpening → half_base → half_specific → half_taper`), each with: `min_weeks`, `max_weeks`, `focus`, `long_run_target_progression`, `quality_intent`, `allowed_intensity_envelope`, `advance_gate_id`.
  - `target` (A-race) with date window and distance.
- `data/plan/races.yaml` — append-only list of races: `{race_id, date, distance, priority(A|B|C), goal(optional), status(planned|done|cancelled)}`. The January half is the seed A-race. The athlete adds 5K/10K Bs/Cs here over time.
- `data/plan/phase_gates.yaml` — objective advance criteria per transition (the M1 gate table), expressed over `AccumulatedState` (v1.7) + consistency metrics.

## v1.8.2 New deterministic module: `src/running_coach/periodization.py`

Pure functions, no clock (reference_date injected), no LLM:

- `derive_phase_schedule(macrocycle, races, today) -> list[PhaseBlock]` — reverse-anchors phases from the A-race, inserts B/C race weeks, returns dated blocks for the rolling horizon (default 8 weeks, min 4).
- `evaluate_phase_gate(gate, accumulated_state, consistency) -> GateResult` — returns `advance | hold | regress` with reasons. Uses v1.7 signals: holds if `bruna_fatigued_week_run >= threshold`, `matheus_achilles_recent_max >= threshold`, or consistency below target; advances only when all criteria pass.
- `plan_horizon(phase_schedule, races, accumulated_state, today) -> list[PlannedWorkout]` — generates the next 4–8 weeks of planned workouts respecting the active phase envelope, weekly_baseline (`cycle.yaml`), and race taper/recovery windows. Regenerates only future rows.

## v1.8.3 Race-aware horizon shaping

For each race within the horizon:
- **Pre-race taper** scaled by priority: A → from `half_taper` phase; B → ~3–5 day mini-taper; C → ≤2 day easing, run through (no goal change). Taper length is a named constant per priority.
- **Post-race recovery** reuses v1.7 `RECOVERY_DAYS_BY_EFFORT` keyed by race distance; propagated as `in_post_race_recovery`.
- **Benchmark capture:** a done race with distance/pace becomes evidence the engine and LLM may cite to recalibrate Bruna's pace bands (ties to A2) — a real-prova data point, explicitly distinct from training estimates.
- **Conflict resolution:** if two races fall within one recovery+taper overlap, the higher priority wins the block; the lower is auto-demoted to C or flagged for manual resolution (fail-closed: never stack two hard efforts).

## v1.8.4 Adding a race mid-cycle (the core UX of the platform)

Flow: athlete adds `{date, distance, priority}` to `races.yaml` (via the Operar frontend or directly) → pipeline re-runs `derive_phase_schedule` + `plan_horizon` → only future planned workouts change → decisions/history untouched. If the race is <2 weeks out and the athlete is in a heavy block, the gate may `hold` advancement and insert a mini-taper instead of new load.

## v1.8.5 Living plan integration with v1.7

- v1.7 produces `AccumulatedState` per workout (load, fatigue, Achilles trend, recovery).
- v1.8 consumes it at two levels: **micro** (the daily envelope, already in v1.7) and **macro** (phase gate hold/advance + horizon regeneration).
- `cycle.yaml current_phase`/`current_week_number` become **derived outputs** written by the pipeline (not hand-edited), advanced only when `evaluate_phase_gate` returns `advance`.

## v1.8.6 LLM role (unchanged contract, richer context)

- `build_llm_request` gains: `active_phase` (focus, intent, envelope), `phase_progress` (week N of M, gate status), `upcoming_races` (next 1–2 with days-out and priority), `benchmark_history` (recent race results).
- The LLM explains/personalizes the session inside the block. The envelope enforcement (DIV-1) now also rejects an LLM action that violates the active phase's `allowed_intensity_envelope` (e.g., proposing race-pace work during `half_base`).

## v1.8.7 Out of scope for v1.8

- Auto-discovery of public race calendars (athlete enters races manually).
- Multi-athlete divergent macrocycles (Matheus vs Bruna run the shared spine; per-athlete divergence is a later epic).
- Weather/altitude/course-specific pacing models.

## v1.8.8 Acceptance (DoD)

1. **Reverse anchoring:** `derive_phase_schedule` with only the A-race yields `half_taper` ending in the target window and `half_specific`/`half_base` preceding it, each within its `min/max_weeks`. Test asserts the last phase abuts the A-race date.
2. **Add-a-race regeneration:** adding a B-race 5 weeks out regenerates future planned workouts to include a mini-taper before and recovery after; past planned/decision rows are byte-identical (append-only invariant test).
3. **Gate holds on fatigue:** with `bruna_fatigued_week_run >= threshold`, `evaluate_phase_gate` returns `hold` (not `advance`); test asserts phase/week do not advance.
4. **Gate advances on readiness:** clean accumulated state + consistency met → `advance`; `cycle.yaml` derived output reflects the new phase.
5. **Conflict resolution:** two A/B races inside one taper+recovery overlap never produce two hard efforts; the lower priority is demoted or flagged (fail-closed test).
6. **Phase envelope binds LLM:** an LLM response proposing race-pace quality during `half_base` is rejected by `validate_llm_response`.
7. **Determinism:** `plan_horizon`/`derive_phase_schedule` are pure — same inputs + reference_date produce identical output (snapshot test).
8. v1.7 invariants (DIV-1, adaptation, fail-closed) remain green.

When 1–8 hold, the platform is a real coach: north-star periodization toward the January half, event-driven around the races you add as you discover them, and continuously corrected by training feedback and real routine.

## v1.8.9 Dependency order

```
v1.7 (adaptive engine) -> prerequisite; phase gates need AccumulatedState.
v1.8.1 data files (macrocycle, races, phase_gates) -> declare the spine.
v1.8.2 periodization.py (derive_phase_schedule, evaluate_phase_gate) -> deterministic core.
v1.8.3 race-aware shaping + v1.8.4 add-a-race regeneration.
v1.8.5 living-plan write-back to cycle.yaml + planned_workouts.csv (future rows only).
v1.8.6 LLM context + phase-envelope enforcement.
```


---

# v1.8 — Periodization Spine & Event-Driven Planning (DRAFT — pending 4 goal-fulfillment passes)

> Platform goal (athlete's words): "Eu dou o objetivo (meia forte, jan/2027) e o feedback contínuo do Garmin; a plataforma sugere os próximos treinos + provas de balizamento, recalibra a cada feedback, e nos leva ao desempenho máximo possível até o fim do ciclo — recomendações baseadas em ciência, não achismo, e simples de usar. Um running coach especialista in the box."

## v1.8.0 Principles

1. **Deterministic spine, LLM skin.** Macrocycle, phase transitions, and where each race sits are decided by versioned data + deterministic rules. The LLM only renders/personalizes the session inside the block the engine placed. The LLM never owns periodization (preserves DIV-1 + safety contract).
2. **Reverse-anchored from the A-race.** Phases derive backward from `target.date_window` (2027-01-24/31). The plan is a **rolling 4–8 week horizon**, re-derived when inputs change — not a fixed sheet to January.
3. **Event-driven, not calendar-fixed.** Races are first-class events the athlete adds when discovered. Add/remove re-derives the affected horizon (mini-taper before, recovery after) WITHOUT mutating past, already-trained workouts.
4. **Append-only history; future is regenerable.** Past workouts/decisions are immutable audit trail. Only future planned workouts regenerate.
5. **Races typed by priority.** A (goal half), B (important tune-up, short taper), C (training/social race, run through). Priority controls taper length and whether the block goal bends.
6. **Science, not vibes.** Every macro rule cites a `science_ref_id` or an explicit `rule_ref`. Pace bands recalibrate from REAL race results, not hardcoded strings.

## v1.8.1 New versioned data

- `data/plan/macrocycle.yaml` — ordered phase ladder, reverse-anchored: each phase has `min_weeks`, `max_weeks`, `focus`, `long_run_target_progression`, `quality_intent`, `allowed_intensity_envelope`, `advance_gate_id`; plus `target` (A-race date window + distance).
- `data/plan/races.yaml` — append-only races: `{race_id, date, distance, priority(A|B|C), goal?, status(planned|done|cancelled), result?}`. The January half is the seed A-race; athlete adds 5K/10K B/C races over time.
- `data/plan/phase_gates.yaml` — objective advance criteria per transition (the M1 gate table), expressed over `AccumulatedState` (v1.7) + consistency metrics.

## v1.8.2 New deterministic module: `src/running_coach/periodization.py`

Pure functions, no clock (reference_date injected), no LLM:

- `derive_phase_schedule(macrocycle, races, today) -> list[PhaseBlock]` — reverse-anchors phases from the A-race, inserts B/C race weeks, returns dated blocks for the rolling horizon (default 8 weeks, min 4).
- `evaluate_phase_gate(gate, accumulated_state, consistency) -> GateResult(advance|hold|regress, reasons)` — uses v1.7 signals: holds on fatigue/Achilles/low consistency; advances only when all criteria pass.
- `plan_horizon(phase_schedule, races, accumulated_state, today) -> list[PlannedWorkout]` — generates next 4–8 weeks respecting active phase envelope, `weekly_baseline` (cycle.yaml), and race taper/recovery. Regenerates only future rows.

## v1.8.3 Race-aware horizon shaping

- **Pre-race taper** by priority: A → from `half_taper` phase; B → 3–5 day mini-taper; C → ≤2 day easing, run through (no goal change). Named constant per priority.
- **Post-race recovery** reuses v1.7 `RECOVERY_DAYS_BY_EFFORT` keyed by race distance; propagated as `in_post_race_recovery`.
- **Benchmark capture:** a done race result becomes evidence to recalibrate Bruna pace bands (ties to A2) — explicitly distinct from training estimates.
- **Conflict resolution (fail-closed):** if two races fall in one taper+recovery overlap, higher priority wins; lower is demoted to C or flagged for manual resolution. Never stack two hard efforts.

## v1.8.4 Adding a race mid-cycle (core UX)

Athlete adds `{date, distance, priority}` to `races.yaml` (Operar frontend or direct) → pipeline re-runs `derive_phase_schedule` + `plan_horizon` → only future planned workouts change → decisions/history untouched. If a race is <2 weeks out during a heavy block, the gate may `hold` advancement and insert a mini-taper instead of new load.

## v1.8.5 Living-plan integration with v1.7

- v1.7 produces `AccumulatedState` per workout.
- v1.8 consumes it at **micro** (daily envelope, v1.7) and **macro** (phase gate hold/advance + horizon regeneration).
- `cycle.yaml current_phase`/`current_week_number` become **derived outputs** written by the pipeline (not hand-edited), advanced only when `evaluate_phase_gate` returns `advance`.

## v1.8.6 LLM role (unchanged contract, richer context)

`build_llm_request` gains `active_phase` (focus/intent/envelope), `phase_progress` (week N of M, gate status), `upcoming_races` (next 1–2 with days-out + priority), `benchmark_history` (recent race results). Envelope enforcement (DIV-1) now also rejects an LLM action violating the active phase's `allowed_intensity_envelope` (e.g., race-pace work during `half_base`).

## v1.8.7 Out of scope for v1.8

Auto-discovery of public race calendars (manual entry); multi-athlete divergent macrocycles (shared spine for now); weather/course pacing models.

## v1.8.8 Acceptance (DoD)

1. **Reverse anchoring:** `derive_phase_schedule` with only the A-race yields `half_taper` ending in the target window, `half_specific`/`half_base` preceding it, each within `min/max_weeks`; last phase abuts the A-race date.
2. **Add-a-race regeneration:** adding a B-race 5 weeks out regenerates future planned workouts with a mini-taper before + recovery after; past planned/decision rows byte-identical (append-only invariant).
3. **Gate holds on fatigue:** `bruna_fatigued_week_run >= threshold` → `hold`; phase/week do not advance.
4. **Gate advances on readiness:** clean state + consistency met → `advance`; `cycle.yaml` derived output reflects new phase.
5. **Conflict resolution:** two A/B races in one taper+recovery overlap never produce two hard efforts (fail-closed).
6. **Phase envelope binds LLM:** race-pace quality proposed during `half_base` is rejected by `validate_llm_response`.
7. **Determinism:** `plan_horizon`/`derive_phase_schedule` pure — same inputs + reference_date → identical output (snapshot).
8. v1.7 invariants (DIV-1, adaptation, fail-closed) remain green.

## v1.8.9 Dependency order

```
v1.7 -> prerequisite (gates need AccumulatedState).
v1.8.1 data files -> declare the spine.
v1.8.2 periodization.py -> deterministic core.
v1.8.3 race-aware shaping + v1.8.4 add-a-race regeneration.
v1.8.5 living-plan write-back (future rows only).
v1.8.6 LLM context + phase-envelope enforcement.
```

---

# Appendix B — Goal-fulfillment traceability (4 verification passes)

Question verified 4x: **when v1.7 + v1.8 are fully implemented, is the platform goal met?** Goal decomposed into 6 must-haves; each pass below attacks from a different angle and lists residual gaps.

## B.0 The goal as 6 testable must-haves

- G1 — Suggests next workouts driven by the objective (not just evaluates a day).
- G2 — Garmin feedback recalibrates next workouts + the week.
- G3 — Benchmark races (5/10k) are addable anytime and reshape the plan.
- G4 — Progresses toward peak performance at the January half (gets more specific over time).
- G5 — Recommendations are science-grounded, not vibes; data analyzed against science.
- G6 — Simple to use.

Pass verdicts and gaps are recorded in §B.1–B.4; unresolved gaps are consolidated in §B.5 and MUST be closed (or explicitly accepted) for the goal to be "met."

## B.1 Verdict (4 passes complete)

**With the spec as written, the goal is NOT yet fully met.** v1.7 + v1.8 deliver a SAFE, ADAPTIVE, EVENT-DRIVEN *container* for periodization. They do NOT yet specify the *content* that drives a real peak. Across all four passes the same conclusion: the deterministic spine is a skeleton without muscles. Per-must-have:

| Goal | Verdict | Why |
|---|---|---|
| G1 suggest workouts from objective | PARTIAL | `plan_horizon` signature exists; the algorithm that picks session type/distance/intensity per slot is unspecified. |
| G2 Garmin feedback recalibrates | MET (by design) | v1.7 §3 is concrete and testable. Caveat: 0% implemented today. |
| G3 races addable + reshape plan | PARTIAL | Add-a-race flow specified; race-result → pace-band recalibration has no method. |
| G4 progress to peak / more specific | PARTIAL | Phases/gates are structural labels; phase CONTENT (`allowed_intensity_envelope`, `quality_intent`, `long_run_target_progression` values) undefined. |
| G5 science, not vibes | MET (micro) / GAP (macro) | v1.7 rules cite refs; periodization/taper/race-prediction have NO refs in the registry. |
| G6 simple to use | PARTIAL | Frontend loop exists; ~24 manual inputs/week, no single "what to do today + why", no race-add UI. |
| **G7 (newly identified)** prescribe concrete pace/distance, not just action categories | MISSING | `RecommendationAction` is abstract (`maintain`/`reduce`...); nothing deterministic validates the LLM's prescribed paces against phase+fitness. |

## B.2 Critical path — gaps that BLOCK peak performance (must close)

These must be added (as v1.8.x content) for the goal to be achievable:

1. **Long-run progression protocol** — concrete distances per phase (e.g., 10→16→18–20 km) with weekly increment cap and step-back. (Passes 1#7, 3#1)
2. **Half-specific workout templates** — current `workout_templates.yaml` has only `easy_run`, `controlled_quality`, `diagnostic_race_10k`. Need HM-pace tempo, progressive long run, HM-pace intervals. (Passes 1#2, 3#3)
3. **`plan_horizon` selection algorithm** — how a phase + weekly_baseline + state maps to concrete sessions per slot. (Passes 1#1, 2#1)
4. **Phase envelope/intent VALUES** — populate `allowed_intensity_envelope`/`quality_intent`/`min_weeks`/`max_weeks` per phase; today they are empty fields. (Passes 1#2, 3#3)
5. **Benchmark race → pace recalibration METHOD** — deterministic (Riegel/VDOT), not LLM-delegated; feeds the next blocks' targets. (Passes 1#3, 2#2, 3#5)
6. **Taper protocol** — duration (10–21 d for a half), volume decay pattern, intensity maintenance; add a taper science ref. (Pass 3#4)
7. **G7 prescriptive validation** — deterministic check that the LLM's prescribed pace/distance fits the active phase + recalibrated bands; reject otherwise. (Pass 1 G7)

## B.3 Reliability/UX gaps (must close for "in the box / simple")

8. **Single daily directive** — a `what_to_do_today` (action + pace/distance + one-line why) in `app-data.json`. (Pass 4#2)
9. **Cold-start week-1** — useful starter suggestion when `insufficient_history` (not "maintain nothing"). (Pass 4#3)
10. **Missed-workout re-plan** — horizon re-derives instead of drifting. (Pass 4#1)
11. **Garmin gap detection** — distinguish "rested" from "ran but didn't export"; do not fire false load spikes. (Pass 4#6)
12. **Minimum-viable check-in** — reduce required inputs; "how do you feel?" as the floor. (Pass 4#4)
13. **Ignored-suggestion escalation** — detect repeated non-compliance, not just react to a load spike. (Pass 4#5)
14. **Race-add UI** in Operar; do not require YAML schema knowledge. (Passes 1#6, 4#7)

## B.4 Wiring/integration gaps (chain breaks)

15. **`consistency` metric undefined** for `evaluate_phase_gate`. Define source + window. (Passes 1#8, 2#3)
16. **Regeneration trigger** — what calls `plan_horizon` after a gate `advance`, and on normal days. (Pass 2#4)
17. **`cycle.yaml` / `planned_workouts.csv` write-back path** (future rows only) + append-only RUNTIME guard, not just a test. (Passes 2#5, 4#8)
18. **Pre-taper readiness gate** for the A-race (long run ≥16 km done, ≥25 km/wk sustained, ≥2 HM-specific sessions). Time alone must not force taper. (Pass 3#7)
19. **Timeline feasibility check** — 34 weeks (2026-05-29 → 2027-01-24) vs sum of phase `min_weeks`; prove slack for holds. (Pass 3#10)
20. **Add periodization science refs** — half prep (Pfitzinger/Daniels), taper (Mujika & Padilla 2003; Bosquet 2007), race prediction (Riegel 1981, Daniels VDOT). Back `conservative-cold-start` and `coaching-principle-deload` rule_refs with rationale docs. (Passes 1#10, 3#8, 4#9)

## B.5 Conclusion

- **v1.7 (adaptive engine)** is well-specified and, once implemented, delivers G2 and the micro-safety layer. It is the correct prerequisite.
- **v1.8 (this draft)** correctly establishes the periodization *skeleton* (reverse anchoring, gates, event-driven races, living plan) but is **content-empty**: it names phases and envelopes without defining the training stimulus that produces a peak.
- **Therefore the goal is met only if a `v1.8.x — Periodization Content` addendum closes B.2 (#1–#7) and B.4 (#15–#20).** B.3 closes the "simple / in the box" requirement.
- Honest framing for the athlete: at the end of THIS spec you get a coach that **trains you safely toward January and adapts to your feedback and races** — but to **maximize performance** (true peak), the content layer (long-run progression, half-specific work, taper, race-based pace calibration) and the periodization science refs must be added. Without them the system maintains fitness conservatively but cannot guarantee peak.

This Appendix is the acceptance gate: the platform goal is "met" when B.2, B.3, and B.4 are closed (or explicitly accepted as deferred with rationale), on top of v1.7 + v1.8 structural DoDs.


---

# v1.8.x — Periodization Content (DRAFT — pending review)

> Purpose: put MUSCLE on the v1.8 skeleton. Closes Appendix B.2 (#1–#7, peak-blocking) and B.4 (#15–#20, integration). Everything here is deterministic and science-cited; the LLM still only personalizes within these bounds.

Grounding facts (verified): 2026-05-29 → 2027-01-24 = **34.3 weeks**. Phase `min_weeks` sum = 20, `max_weeks` sum = 31 → fits 34 with 3–14 weeks slack for holds (timeline feasible, closes B.4#19). Current long-run ceiling from real Garmin data ≈ **9 km** → the gap to ~18–20 km half-specific endurance is the central training problem. Athlete pattern: 3 runs/week (Tue/Thu/Sun), Achilles-limited. **Weekly volume is NOT a fixed 20–30 km — it is a derived, progressive target that rises from the athlete's real current baseline toward a peak (see v1.9.A). The long-run share cap (X.2) implies peak weekly volume ≈ LONG_RUN_PEAK / share ≈ 40 km on 3 runs (≈ 20 long + 2×10). v1.7 constants below were drafted against a static-volume assumption and are re-grounded by v1.9.A.**

## X.1 Phase content table (closes B.2#4, fills `macrocycle.yaml` values)

Reverse-anchored from the A-race. `quality_intent` and `allowed_intensity_envelope` are the deterministic envelope the LLM cannot exceed.

| Phase | min/max wk | focus | weekly quality cap | allowed_intensity_envelope | long-run target (end of phase) |
|---|---|---|---|---|---|
| `base` | 4 / 8 | aerobic base, durability | 0 (all easy) | `{easy}` | 10 → 12 km |
| `five_ten_k_sharpening` | 4 / 6 | speed/economy at 5–10k | 1 | `{easy, threshold, intervals_5_10k}` | 12 → 14 km |
| `half_base` | 6 / 8 | aerobic ceiling + tempo | 1 | `{easy, tempo_hmp, long_progressive}` | 14 → 18 km |
| `half_specific` | 4 / 6 | half-marathon specificity | 2 (long counts as 1) | `{easy, tempo_hmp, hmp_intervals, long_progressive}` | 18 → 20–21 km |
| `half_taper` | 2 / 3 | freshness, keep intensity | 1 (short) | `{easy, hmp_intervals_short}` | reduce to 12–14 km |

Rule: the active phase's `weekly quality cap` overrides the v1.7 `intensity_overreach` count (closes B.2 / Pass 3#6 — a progressive long run in `half_specific` must NOT lock the athlete to one quality session). In `half_specific`, `quality_sessions_last_7d >= 3` triggers `intensity_overreach`, not `>= 2`.

## X.2 Long-run progression protocol (closes B.2#1)

Deterministic, reversible, Achilles-aware. Constants:

```python
LONG_RUN_START_KM = 9.0          # current real ceiling
LONG_RUN_PEAK_KM = 20.0          # half-specific endurance target
LONG_RUN_WEEKLY_STEP_KM = 1.5    # max increase on a building week
LONG_RUN_STEPBACK_EVERY = 3      # every 3rd week is a step-back...
LONG_RUN_STEPBACK_FRACTION = 0.70  # ...at 70% of the prior long run
LONG_RUN_SHARE_CAP = 0.50        # long run <= 50% of weekly volume (3x/week reality)
```

`plan_horizon` sets each week's long run = min(prev_building_long + STEP, PEAK), inserting a step-back every 3rd week, never exceeding `LONG_RUN_SHARE_CAP` of planned weekly volume. If `matheus_achilles_recent_max >= 3` or a deload is active, the long run holds (no increase) that week. Cite `load-management-recovery` (reversible progression) + `rule_ref: long-run-progression`.

## X.3 Half-specific workout templates (closes B.2#2; extends `workout_templates.yaml`)

Add templates with explicit intensity bound to recalibrated pace bands (X.4):

- `tempo_hmp`: 15–25 min continuous at half-marathon pace (HMP). contraindications `[red_flag, achilles_ge_3, poor_sleep]`. tags `[threshold, race_calibration]`.
- `hmp_intervals`: e.g., 3–5 × (2 km @ HMP, 2–3 min jog). contraindications same + `volleyball_previous_day_max`. tags `[threshold, race_calibration]`.
- `hmp_intervals_short` (taper): 3–4 × (1 km @ HMP). keeps intensity, low volume.
- `long_progressive`: easy first 70%, final 30% at HMP. counts as 1 quality. tags `[long_run, race_calibration]`.
- `intervals_5_10k`: 5–8 × (1 km @ ~10k pace). only in `five_ten_k_sharpening`. tags `[threshold, intensity_distribution]`.

The deterministic spine selects the template per slot (X.5); the LLM only fills exact reps/recoveries within the template's bounds.

## X.4 Benchmark race → pace recalibration METHOD (closes B.2#5, B.3 pace truth)

Deterministic, NOT LLM-delegated. On a `done` race in `races.yaml` with `result` (distance + time):

```
Riegel: T2 = T1 * (D2 / D1) ** 1.06      # predicted time at distance D2
HMP   = predicted half time / 21.0975    # sec per km
```

- Compute predicted HMP and easy/threshold bands from the most recent benchmark (≤8 weeks old; prefer 10k > 5k for half prediction).
- Write bands to `data/plan/pace_bands.yaml` (versioned, derived). `_athletes()` in `frontend_data.py` reads this file instead of hardcoded strings (closes A2 properly).
- Bands carry `source` (`race:<race_id>` vs `estimate`) and `as_of` date for auditability.
- Cite new ref `race-time-prediction-riegel`. Sanity guard: reject a predicted improvement > 8% vs prior band in one step (fail-closed against a fluke/mismeasured race) → flag for manual confirmation.

## X.5 `plan_horizon` selection algorithm (closes B.2#3, B.4#16)

Deterministic per week, given active phase + weekly_baseline + accumulated_state:

```
for each run slot in weekly_baseline (Tue/Thu/Sun):
  Sunday  -> long run (distance from X.2; long_progressive if phase allows quality and long-quality due)
  one mid-week slot -> the phase's quality template IF weekly quality cap not exceeded AND no active reduce/deload/achilles block
  remaining slots -> easy_run (pace from X.4 easy band)
apply race taper/recovery shaping (v1.8.3) on top
```

Triggers (B.4#16): `plan_horizon` runs (a) when a race is added/removed, (b) when `evaluate_phase_gate` returns `advance`, (c) on the first pipeline run of each ISO week. It regenerates only rows with `date > today` (append-only, X.8).

## X.6 Prescriptive validation — G7 (closes B.2#7)

The LLM prescribes concrete pace/distance in `next_workout`. Add deterministic checks in `validate_llm_response`:

- Parse the prescribed pace/distance; reject if pace is faster than the recalibrated band for the prescribed intent (e.g., "easy" faster than easy band), or if distance exceeds the phase long-run target +10%.
- Reject any HMP/interval prescription when the active phase envelope (X.1) does not allow it (closes v1.8.6 with concrete envelope values).
- If parsing fails, downgrade `confidence` and require `request_manual_resolution` (fail-closed).

## X.7 Pre-taper readiness gate + consistency metric (closes B.4#15, B.4#18)

`consistency` (B.4#15) is defined as: completed_runs / planned_runs over the trailing 4 ISO weeks (0–1), from `plan_status` matched workouts. Used by `evaluate_phase_gate`.

Pre-taper readiness gate (B.4#18) — entering `half_taper` requires ALL:
- a long run ≥ 16 km completed in the last 4 weeks,
- ≥ 25 km/week sustained in ≥ 3 of the last 4 weeks,
- ≥ 2 half-specific quality sessions completed in `half_specific`,
- `matheus_achilles_recent_max <= 2`.

If time forces the taper window but readiness fails → enter taper anyway (cannot move the race) but emit `decision: race_strategy` with reason `entered_taper_underprepared` and set goal expectation to "complete strong, not peak" (honest, fail-closed). Cite `rule_ref: half-readiness-gate`.

## X.8 Living-plan write-back + append-only runtime guard (closes B.4#17)

- Pipeline writes derived `current_phase`/`current_week_number` to `cycle.yaml` only when the gate advances; `current_week_number` increments per ISO week regardless.
- `plan_horizon` write to `planned_workouts.csv` is guarded by `assert_append_only(old_rows, new_rows)`: any row with `date <= today` must be byte-identical; raise `PipelineError` otherwise. This is a RUNTIME guard, not just a test (Pass 4#8).

## X.9 New science references (closes B.2#6, B.4#20; add to `science_refs.yaml`)

| science_ref_id | source | used for |
|---|---|---|
| `riegel-race-prediction` | Riegel, "Athletic Records and Human Endurance," Am. Scientist 1981 | X.4 pace recalibration |
| `daniels-vdot-pacing` | Daniels, "Daniels' Running Formula" 3rd ed. | pace band sanity / training intensities |
| `taper-performance-mujika` | Mujika & Padilla, "Scientific bases for precompetition tapering," MSSE 2003 | X.10 taper |
| `taper-meta-bosquet` | Bosquet et al., "Effects of tapering on performance: a meta-analysis," MSSE 2007 | X.10 taper volume decay |
| `half-marathon-prep-pfitzinger` | Pfitzinger & Douglas, "Faster Road Racing" | long-run + HMP specificity |

`rule_ref` docs (rationale, not science): `long-run-progression`, `half-readiness-gate`, `coaching-principle-deload`, `conservative-cold-start` — add short markdown rationales under `docs/` (closes Pass 4#9).

## X.10 Taper protocol (closes B.2#6)

```python
TAPER_DAYS_A = 14            # 2-week taper for the half (within Mujika 7-21d range)
TAPER_VOLUME_DECAY = "exp"   # exponential decay outperforms linear (Bosquet 2007)
TAPER_WEEK1_VOLUME = 0.70    # of pre-taper weekly volume
TAPER_WEEK2_VOLUME = 0.50
TAPER_KEEP_INTENSITY = True  # maintain 1 short HMP session/week; cut volume not sharpness
```

`half_taper` phase applies this: volume decays exp to ~50%, intensity preserved via `hmp_intervals_short`. Cite `taper-performance-mujika` + `taper-meta-bosquet`.

## X.11 Acceptance (DoD) for the content layer

1. **Timeline feasibility:** assert sum of phase `min_weeks` (20) ≤ weeks-to-A-race (34) at plan creation; raise if infeasible.
2. **Long-run progression:** snapshot test from 9 km → 20 km with step-backs every 3rd week, never > 50% weekly volume, holds when Achilles ≥ 3 or deload active.
3. **Recalibration math:** Riegel test — 10k @ 50:00 → HMP within expected band; improvement > 8% in one step is rejected/flagged.
4. **Phase envelope binds prescription:** LLM prescribing HMP intervals during `base` is rejected; easy faster than easy band is rejected (G7).
5. **Quality cap by phase:** in `half_specific`, 2 quality sessions/week allowed (long_progressive + 1 tempo); a 3rd triggers `intensity_overreach`.
6. **Readiness gate:** entering `half_taper` without a ≥16 km long run in 4 weeks → `entered_taper_underprepared` + "complete strong, not peak"; never silently advances as if peaked.
7. **Append-only runtime guard:** attempting to rewrite a past planned row raises `PipelineError`.
8. **Consistency metric:** completed/planned over trailing 4 weeks computed and feeds `evaluate_phase_gate`.
9. **Science citations:** every new rule cites a `science_ref_id` or a documented `rule_ref`; no rule cites a ref whose finding does not support it (re-run the S12 check).

## X.12 Goal status after this layer

With v1.7 + v1.8 + v1.8.x implemented and DoDs green, Appendix B.2 and B.4 close. The platform then: (G1) suggests concrete sessions from the objective; (G2) recalibrates from Garmin feedback; (G3) reshapes around added races AND recalibrates paces from real results; (G4) progresses phase-by-phase to a real half-specific peak with a science-based taper; (G5) every decision is science- or rule-cited; (G7) prescriptions are pace/distance-concrete and bounded. B.3 (single daily directive, cold-start, missed-workout re-plan, gap detection, minimal check-in, race-add UI) remains the "simple / in the box" UX layer — recommended as v1.9, and is the last gate before the goal is fully met end-to-end.

## X.13 Review log

- Pass A (sports-science peak realism): PENDING
- Pass B (determinism/feasibility/integration): PENDING


---

# v1.8.z — Change Explainability Contract (cross-cutting; DRAFT — pending review)

> Athlete requirement: whenever periodization OR a workout changes, the platform must say — based on what, which source/study, why, and what the gain is for the MICRO objective (next session) and the MACRO objective (the January half). A real "coach in the box" justifies every change.

## Z.0 Principle: facts are deterministic, prose is LLM

The explanation's **factual fields** (trigger, source/study, what changed, micro/macro objective, expected gain, cost) are produced by the deterministic engine from the triggering reason. The LLM only renders them into readable Portuguese. The LLM never selects the citation and never invents a study. This preserves the audit contract and DIV-1.

## Z.1 `ChangeExplanation` schema (attached to every change)

Emitted whenever a decision differs from the plan/default (workout change) OR a phase gate advances/holds/regresses OR the horizon is regenerated (race added, gate change).

```python
class ChangeExplanation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope: Literal["workout", "periodization"]      # micro vs macro change
    change_id: str
    what_changed: str                                # "Quinta: tempo HMP -> corrida leve"
    from_state: str                                  # prior planned action/phase
    to_state: str                                    # new action/phase
    trigger: list[str]                               # engine reason tags, e.g. ["weekly_load_spike"]
    trigger_evidence: dict                           # the numbers: {"load_ratio":1.34,"prior_mean_km":28,"last_7d_km":37}
    sources: list[SourceCitation]                    # studies/rules backing the change (see Z.2)
    why: str                                         # one paragraph reasoning (LLM-rendered from facts)
    micro_objective: str                             # gain for the NEXT session
    macro_objective: str                             # gain for the January-half cycle
    expected_gain: str                               # what improves
    cost_or_tradeoff: str                            # honest downside (e.g., "perde 1 estímulo de qualidade")
    confidence: Confidence
    missing_evidence: list[str]
```

```python
class SourceCitation(BaseModel):
    ref_id: str                # science_ref_id OR rule_ref id
    kind: Literal["science", "rule"]
    title: str                 # from registry (science) or rationale doc (rule)
    doi_or_url: str | None     # science only
    finding: str               # registry finding (science) or rationale (rule)
    applies_because: str       # one line tying THIS finding to THIS change
```

## Z.2 Source resolution (deterministic; closes the hallucination hole)

- For each `trigger` reason tag, the engine resolves sources via the EXISTING map `recommendations.py::_rule_refs_for` (science) plus a new `rule_ref` map for heuristics (`long-run-progression`, `half-readiness-gate`, `coaching-principle-deload`, `conservative-cold-start`).
- `SourceCitation.title/doi_or_url/finding` are read from `data/knowledge/science_refs.yaml` (science) or from the rule rationale docs under `docs/` (rules). NEVER from the LLM.
- **Invariant EXPL-1 (anti-decoration):** the set of `sources[].ref_id` MUST equal the engine-attached refs for the triggering reasons — not a superset. `validate_llm_response` rejects any explanation citing a ref the deterministic reason did not map to (extends the existing approved-refs check, which today only enforces ⊆ approved; this tightens it to "= engine-mapped for the active reasons").

## Z.3 Micro vs macro objective (both always present)

- **scope="workout" (micro change):** `micro_objective` = immediate intent (e.g., "absorver a carga da semana e proteger o Aquiles"); `macro_objective` = how skipping/reducing today protects the cycle (e.g., "preserva a progressão de longão rumo aos 20 km e a janela da meia em janeiro").
- **scope="periodization" (macro change):** `from_state`/`to_state` are phases (e.g., `half_base → half_specific`); `micro_objective` = what this week's sessions now target; `macro_objective` = the phase's role toward the half (X.1 `focus`). A gate `hold` is also a change and must be explained ("segurando a fase: consistência 0.6 < alvo; ganho = não avançar sobre base incompleta").

## Z.4 Production & wiring

- The deterministic engine builds a `ChangeExplanation` skeleton with all factual fields populated (trigger, trigger_evidence, sources, from/to, micro/macro objective stubs from phase/reason metadata, cost).
- `build_llm_request` includes the skeleton; the LLM fills only `why`, and polishes `micro_objective`/`macro_objective`/`expected_gain`/`cost_or_tradeoff` into prose WITHOUT changing the cited sources or numbers.
- `validate_llm_response` enforces EXPL-1 and that `trigger_evidence` numbers are unchanged from the skeleton (LLM cannot alter facts).
- Persisted to `data/processed/decisions.csv` (new columns) and `reports/llm/`. Surfaced in `app-data.json` so the frontend shows it.

## Z.5 Frontend surfacing (Coach Room + Timeline)

- Each changed workout in Timeline and each recommendation in Coach Room shows: the one-line `what_changed`, an expandable "Por quê" with `why` + `micro_objective` + `macro_objective` + `expected_gain` + `cost_or_tradeoff`, and the `sources` as clickable study links (DOI) with `finding` + `applies_because`.
- No change without an explanation: if a change has no `ChangeExplanation`, the frontend shows a "sem justificativa" warning (fail-loud), and a test forbids it.

## Z.6 Acceptance (DoD)

1. **Every change carries an explanation:** test that any decision where `action != planned_action`, any gate non-`advance`-with-change, and any horizon regeneration produces a `ChangeExplanation` with all required fields non-empty.
2. **Anti-hallucination (EXPL-1):** an LLM explanation citing an approved-but-unmapped ref is rejected; a science citation's `doi_or_url`/`finding` match the registry byte-for-byte (LLM cannot alter them).
3. **Facts immutable by LLM:** test that `trigger_evidence` numbers and `sources` in the output equal the engine skeleton; only prose fields differ.
4. **Both objectives present:** micro_objective AND macro_objective non-empty for both scopes; a `hold` gate explains why holding helps the macro goal.
5. **Honest cost:** `cost_or_tradeoff` non-empty for any reduce/defer/off change (no change is sold as pure upside).
6. **Frontend no-silent-change:** a changed workout without an explanation triggers the fail-loud warning (tested).
7. **Rule rationale docs exist:** each `rule_ref` used has a markdown rationale under `docs/`; the S12 check passes (no science ref cited for a heuristic it does not support).

## Z.7 Example (illustrative, scope="workout")

```
what_changed: "Quinta: tempo em ritmo de meia -> corrida leve 6 km"
from_state: tempo_hmp ; to_state: replace_with_easy
trigger: ["weekly_load_spike"]
trigger_evidence: {load_ratio: 1.34, prior_mean_km: 28, last_7d_km: 37, abs_delta_km: 9}
sources: [{ref_id: load-management-recovery, kind: science,
           title: "IOC consensus statement on load in sport and risk of injury",
           doi_or_url: "https://doi.org/10.1136/bjsports-2016-096581",
           finding: "Rapid load changes and inadequate recovery increase injury risk.",
           applies_because: "Volume subiu 34% vs média de 4 semanas; estímulo extra agora aumenta risco."}]
why: "Sua carga dos últimos 7 dias saltou de ~28 para 37 km. Adicionar qualidade hoje empilha risco sem ganho proporcional."
micro_objective: "Absorver a carga e chegar inteiro ao longão de domingo."
macro_objective: "Proteger a progressão de longão (rumo a 20 km) e a janela da meia em janeiro; consistência > heroísmo."
expected_gain: "Recuperação que sustenta a próxima semana de qualidade."
cost_or_tradeoff: "Perde 1 estímulo de tempo nesta semana; recuperável na próxima."
confidence: medium
```

## Z.8 Review log (1 pass complete; findings integrated below)

Integrated corrections (override the drafts above where they conflict):

- **EXPL-1 relation (F2, F8):** change from "MUST EQUAL" to **"sources[].ref_id MUST be a non-empty SUBSET of the engine-mapped refs for the active reasons"** (LLM may explain a subset of reasons). `validate_llm_response` enforces this against `request["deterministic_guardrail"]["science_refs"]`/`["rule_refs"]` (it currently only checks ⊆ approved — tighten to ⊆ engine-mapped AND non-empty).
- **Split refs by kind (F9, F2):** split `recommendations.py::_rule_refs_for` into `_science_refs_for(reasons)` and `_rule_refs_for(reasons)` (today both fields get the same list). Add explicit mappings for ALL accumulated reasons BEFORE Z.0: `weekly_load_spike→science:load-management-recovery`, `intensity_overreach→science:seiler-intensity-distribution`, `achilles_trend_block/achilles_trend_reduce→science:achilles-tendinopathy-load`, `post_race_recovery→science:load-management-recovery`, `consecutive_fatigue_deload→rule:coaching-principle-deload`, `insufficient_history→rule:conservative-cold-start`. No accumulated reason may fall through to the `training-consistency-principle` fallback.
- **Prose anti-hallucination (F1):** prose fields (`why`, objectives, gain, cost) are linted — extract citation patterns (DOI regex, `et al.`, `(YYYY)`, registry author surnames); reject if any candidate is not a `sources[].ref_id` in the same explanation. Prompt instructs the LLM to NEVER name a study in prose, only reference via `sources[]`.
- **`rule_refs.yaml` registry (F3):** create `data/knowledge/rule_refs.yaml` (parallel to `science_refs.yaml`): `{rule_ref_id, title, rationale, applies_to}`. Populate `coaching-principle-deload`, `conservative-cold-start`, `long-run-progression`, `half-readiness-gate` BEFORE implementing Z.0. Startup validation: every `rule_ref` emitted by the engine has an entry. `SourceCitation` for rules reads title/finding from here.
- **trigger_evidence immutability (F4, F10):** engine **rounds all numeric `trigger_evidence` to 2 decimals at skeleton-build time**; the engine (not the LLM) populates `sources[].finding`/`doi_or_url` from the registry into the skeleton. Validation compares the LLM output against the **skeleton's serialized form** (key set identical; byte-equal after rounding) — not against a fresh YAML read.
- **Definition of "change" (F5):** a `ChangeExplanation` is required iff `action != planned_action` AND `planned_action` came from a real planned workout (`planned_workout_id != "unplanned-next-workout"`). First-ever/unplanned defaults need no explanation (no false positives on cold-start).
- **Deterministic fallback when LLM skipped (F6):** when `run_llm=false`/Bedrock skipped, the engine fills prose from reason+phase metadata templates (`why`, `micro_objective`, `macro_objective` stubs), sets `confidence=low`, adds `"llm_unavailable"` to `missing_evidence`. The contract holds without Bedrock.
- **macro_objective noise (F7):** `macro_objective` is `str | None`; REQUIRED only when `scope=="periodization"` OR the change has a multi-day effect (deload, phase hold, race recovery). Routine single-workout transient changes (`poor_sleep`, `volleyball_previous_day`) may use a canned one-liner or `null`.

Updated DoD (supersedes Z.6 where conflicting):
- DoD #2 → EXPL-1 as SUBSET-of-engine-mapped + non-empty; LLM citing an approved-but-unmapped ref is rejected.
- DoD #3 → `trigger_evidence` equal within rounding; `sources[].finding`/`doi_or_url` equal to skeleton.
- New DoD #8 → prose lint rejects a fabricated `(Autor, ano)`/DOI not present in `sources[]`.
- New DoD #9 → with `run_llm=false`, explanations still validate (templated prose, `confidence=low`, `llm_unavailable` flagged).
- New DoD #10 → `rule_refs.yaml` exists and every emitted `rule_ref` resolves; `kind` is correct (no heuristic presented as science — S12).

Residual accepted: prose lint is heuristic (catches author-year/DOI patterns, not arbitrary unattributed claims). Mitigated by: facts/sources are engine-owned and the LLM is instructed/validated to reference only `sources[]`. Full semantic claim-checking is out of scope.


---

# v1.9.A — Progressive Volume (derived, not hardcoded) (DRAFT)

> Athlete correction: weekly km is NOT hardcoded at 30. It must rise progressively and realistically toward race prep, and must FIT the real routine. Volume is a derived target, bounded by safe ramp rules and by what the week actually allows.

## A.1 Volume is a function, not a constant

Replace any fixed "20–30 km/week" assumption. Define:

```python
def target_weekly_km(baseline_km: float, phase: Phase, week_idx: int, accumulated: AccumulatedState) -> float
```

- `baseline_km` = the athlete's REAL trailing 4-week mean (from history, not a literal). Cold-start uses the last 2–3 weeks or a conservative floor.
- Ramp obeys v1.7 safety: weekly increase capped so `load_ratio` stays ≤ `LOAD_RATIO_CAP` (1.15) AND absolute jump ≤ `LOAD_ABS_FLOOR_KM` is NOT exceeded as a *spike* (i.e., plan rises ~8–10%/week, never triggering `weekly_load_spike`). The progression and the guardrail use the SAME constants — the plan ramps just under the cap by construction.
- Phase shapes the curve: `base`/`half_base` build volume; `half_specific` holds volume and shifts toward specificity; `half_taper` cuts volume (X.10) while keeping intensity.
- `accumulated` gates it: deload, Achilles ≥3, fatigue, or `insufficient_history` → hold or lower the target that week (never raise).

## A.2 Peak volume is derived from the goal, not declared

- Peak weekly volume emerges from `LONG_RUN_PEAK_KM` and `LONG_RUN_SHARE_CAP`: `peak_week ≈ LONG_RUN_PEAK / LONG_RUN_SHARE` (≈ 20 / 0.5 = 40 km on 3 runs). This RESOLVES the arithmetic conflict the review found (20 km long run is impossible at 50% share if the week stays 30 km — the week must grow to ~40 km).
- If the athlete cannot sustain the implied peak within the real routine (only 3 slots, Achilles), the system lowers the long-run peak target and resets the half goal to "complete strong," emitting a `ChangeExplanation` (Z) — honest, not silent.
- **Adding a 4th run** is an option the system may SUGGEST (not force) when 3 slots cannot carry the required volume safely; gated behind Achilles status and the athlete accepting it in the routine.

## A.3 Fits the real routine (the hard constraint)

- The plan never schedules volume the `weekly_baseline` (cycle.yaml) cannot hold. Volume rises by lengthening existing runs and, only if accepted, adding a slot — not by inventing sessions on strength/volleyball days.
- Volleyball (Wed) and strength (Mon/Fri) remain load inputs (v1.7), so the runnable volume ceiling is lower than a pure-runner's. `target_weekly_km` accounts for total load, not just running km.

## A.4 DoD

1. No constant equals a fixed weekly km; `target_weekly_km` is derived from real `baseline_km`.
2. Snapshot: from a real ~9 km long / low base, volume ramps to ~40 km peak by `half_specific` WITHOUT ever firing `weekly_load_spike` (progression ≤ cap by construction).
3. Achilles ≥3 / deload / insufficient_history weeks show held-or-lower target.
4. If peak is unreachable in 3 slots, the system emits a goal-reset `ChangeExplanation`, never a silent shortfall.
5. Taper reduces volume per X.10 while the derived peak is respected before it.

---

# v1.9.B — LLM as orchestrated science engine (role definition) (DRAFT)

> Athlete intent: there are MANY years of proven training science online; a high-capability model (Opus-class) should USE that knowledge assertively. Our system ORCHESTRATES it. The LLM is the reasoning engine over science; the deterministic spine is the safety/orchestration boundary.

## B.1 Division of authority (precise)

| Concern | Owner | Why |
|---|---|---|
| Safety stops (red flag, PSE≥9, Achilles, load spike) | Deterministic engine | Must be auditable, fail-closed, never overridden by a model. |
| Phase placement, gates, volume ramp, taper math | Deterministic engine | Periodization is structural and time-anchored. |
| Pace recalibration (Riegel/VDOT) | Deterministic engine | Numbers must be reproducible. |
| **Session design WITHIN the phase envelope** | **LLM** | Where broad training science adds value: exact reps, structure, cues, variety. |
| **Reasoning/justification, applying literature** | **LLM** | Opus-class synthesis of established training science. |
| Which source is cited as the binding rule | Deterministic engine | Anti-hallucination (Z, EXPL-1). |

The LLM may reason from broad training knowledge to DESIGN and EXPLAIN, but any binding safety/periodization CITATION must resolve to the registry. The LLM proposes; the engine disposes and validates.

## B.2 Two tiers of science (resolves "only 9 refs" limitation)

- **Tier 1 — Binding registry** (`science_refs.yaml` + `rule_refs.yaml`): the small, curated, DOI-backed set that governs SAFETY and PERIODIZATION decisions. Closed-world: a guardrail may only cite Tier 1.
- **Tier 2 — Open training knowledge** (the LLM's trained-in literature): used to enrich SESSION DESIGN and EXPLANATION prose, clearly labeled as `general_training_knowledge`, never as a binding safety citation. When the LLM leans on a Tier-2 idea that recurs and proves useful, it is a candidate for promotion to Tier 1 via a human-reviewed registry add (B.4).

This lets the model "use the years of science" assertively for HOW to train, while the safety envelope stays governed by the curated, auditable set.

## B.3 Guardrails on the LLM (so capability ≠ risk)

- Output schema-validated; actions bounded by the phase envelope (X.1) and the deterministic guardrail (DIV-1).
- Prescriptions bounded by recalibrated pace bands and long-run target (X.6/G7).
- Prose citations linted (Z, F1). Tier-2 claims must be labeled, not dressed as registry findings.
- The LLM cannot raise the envelope, add volume beyond the ramp, or introduce intensity a phase forbids — it can only shape within bounds.

## B.4 Science promotion loop (keeps it growing, curated)

- The LLM may emit `suggested_science: [{claim, why_useful, would_change}]` (non-binding).
- These are logged to `reports/llm/science-suggestions.md` for human review; an approved one is added to `science_refs.yaml` with DOI and becomes Tier-1 binding. The system gets smarter over time WITHOUT the model silently inventing authority.

## B.5 DoD

1. A guardrail/periodization decision never cites a non-registry source; a Tier-2 idea in prose is labeled `general_training_knowledge` and is not in `sources[]` as binding.
2. The LLM can vary session design (reps/structure) run-to-run within the same phase envelope (test shows variation without envelope violation).
3. `suggested_science` is captured and never auto-promoted; promotion requires a registry edit.
4. All B.3 bounds enforced by `validate_llm_response`.

---

# v1.9.C — Guardrails & useful additions (final analysis pass)

> Requested final pass: things that may be useful, guardrails, given this becomes a science-based LLM coach orchestrated by our system. Severity-ordered.

1. **Heat/humidity for a January race (Brazil = summer).** HIGH. The A-race window (Jan 2027) is peak Brazilian summer; the current Garmin data shows many runs already flag heat. Guardrail: a `heat_context` input (temp/humidity or a simple flag) that, when high, (a) shifts pace targets to effort/PSE-based not pace-based, (b) blocks chasing pace in the recommendation, (c) is a `race_strategy` note for race day. Cite a thermoregulation/heat-acclimation ref (add to registry). Without this, the plan optimizes pace the athlete cannot hit in the heat.

2. **Strength/volleyball as quantified weekly load, not just a day flag.** HIGH. Mon/Fri strength + Wed volleyball are real neuromuscular load (already refs in registry). Guardrail: include them in `target_weekly_km`'s total-load budget and in fatigue windows, so running volume ramps account for the non-running load. Prevents over-ramp when the week is already loaded off the run.

3. **Minimum-stimulus floor (under-training guard).** MEDIUM. The system is heavily fail-closed; add the symmetric guard: if guardrails keep reducing and the athlete is chronically UNDER the stimulus needed for the phase (e.g., 0 quality for 3 weeks in `half_specific`), flag `under_stimulus` — the coach should say "we're playing too safe to peak." Honest both ways.

4. **Non-compliance / reality drift detection.** MEDIUM. If executed workouts repeatedly diverge from prescribed (athlete runs harder/longer than told, or skips), detect it and adapt the plan to the REAL behavior instead of re-prescribing the ignored plan. Ties to Pass 4#5.

5. **Two-athlete divergence (Matheus vs Bruna).** MEDIUM. They share runs but have different limiters (Matheus Achilles; Bruna is the performance target). The spine is shared today; guardrail: per-athlete pace bands and per-athlete readiness, so a shared run is easy-for-Matheus / quality-for-Bruna without conflating evidence (preserves the Matheus-only contract).

6. **Illness / life-stress quick input.** MEDIUM. A one-tap "doente / estressado / viajando" that triggers conservative handling for N days — common reality the Garmin can't see.

7. **Long-run quality vs Achilles conflict.** MEDIUM. Progressive long runs (HMP finish) raise Achilles risk exactly when volume peaks. Guardrail: when `matheus_achilles_recent_max >= 3`, the progressive-finish is removed but the easy long distance is preserved (protect tendon, keep endurance).

8. **Data-quality / outlier guard on Garmin import.** LOW-MED. GPS spikes, treadmill 0-distance, paused-watch durations already appear in the CSV. Guardrail: sanity-filter implausible pace/distance before they pollute `AccumulatedState` (a 3:00/km "run" must not recalibrate bands).

9. **Confidence decay on stale evidence.** LOW. If no check-in/Garmin for >10 days, confidence decays and the next suggestion is conservative + asks for a fresh check-in rather than assuming continuity.

10. **Race-week logistics & taper-anxiety note.** LOW. In `half_taper`, the coach should explicitly say reduced volume is intentional (athletes panic during taper) — a `ChangeExplanation` macro_objective that frames the taper as performance, not detraining.

## C.1 DoD (for the ones adopted into the build)

- Heat guard (#1): high `heat_context` switches recommendation to effort-based and blocks pace-chasing; tested. New heat ref in registry.
- Total-load budget (#2): `target_weekly_km` lowers runnable volume when strength/volleyball load is high; tested.
- Under-stimulus (#3): 3 weeks no quality in `half_specific` emits `under_stimulus`; tested.
- Outlier guard (#8): an implausible activity is excluded from `AccumulatedState` and pace recalibration; tested.
- Each adopted guardrail cites a registry `science_ref_id` or documented `rule_ref` (no vibes).

## C.2 Recommended sequencing

```
v1.7 (adaptive engine) -> v1.8 (spine) -> v1.8.x (content) -> v1.8.z (explainability)
-> v1.9.A (progressive volume; folds the static-volume correction into v1.7/v1.8.x constants)
-> v1.9.B (LLM role + two-tier science) -> v1.9.C #1,#2,#8 (heat, total-load, outlier) as first guardrails.
```


---

# Review log — Passes A/B/C (v1.8.x + v1.9 reconciliation, FINAL)

Three specialized passes (peak realism, determinism/integration, v1.9 coherence) reviewed v1.8.x + v1.9.A/B/C against v1.7 and the code. Corrections below are **binding** and override any conflicting draft text above. Grouped by theme.

## R.1 Volume ramp must be PROVABLY under the spike guardrail (was false as drafted)

- **Single source of truth (B-F10, B-F7):** `v1.9.A target_weekly_km` baseline = `accumulated.prior_28d_mean_7d_distance_km` (the exact denominator the guardrail uses). No separate "trailing 4-week mean."
- **Post-stepback cap (B-F1, CRITICAL):** my claim "ramps under the cap by construction" was WRONG — a step-back depresses the trailing mean, so resuming at the prior peak fires `weekly_load_spike`. Fix: the post-stepback week caps at `prior_28d_mean * LOAD_RATIO_CAP`, NOT "prior peak + step." Add `POST_STEPBACK_RAMP_CAP = LOAD_RATIO_CAP`. DoD: after any step-back, the next planned target never triggers `weekly_load_spike` against the actual trailing mean.
- **Absolute increments, not %, at low volume (A-F8):** plan uses fixed km steps (proactive): ≤+2 km/wk when baseline <25; ≤+3 when 25–35; ≤+4 when >35. `LOAD_RATIO_CAP` stays the reactive guardrail. Safer for the Achilles tendon at low volume than a flat percentage.
- **Co-derive long-run step with weekly step (B-F10/A long-run share):** require `weekly_step >= LONG_RUN_WEEKLY_STEP_KM / LONG_RUN_SHARE_CAP` (=3 km) on long-run building weeks; if the safe ramp can't sustain it, reduce the long-run step proportionally. DoD: at no point does planned long run exceed `LONG_RUN_SHARE_CAP` of planned weekly volume.

## R.2 Long-run progression must fit the timeline and the tendon

- **Span ALL phases (A-F1, A-F7):** the 9→20 km progression runs across `base + five_ten_k + half_base + half_specific` (≈26 building weeks), NOT just half_base+half_specific (infeasible at 1.5 km/step). X.1 phase long-run numbers are **end-of-phase exit targets**; the entry is the prior phase's exit. Note added to X.1/X.2.
- **Per-session Achilles cap (A-F2, supersedes v1.9.C#7):** the 20 km distance ITSELF is the tendon risk, not just the progressive finish. Add `LONG_RUN_ACHILLES_CAP_KM = 16`: when `matheus_achilles_recent_max >= 2` for ≥3 of last 4 weeks, cap the long run at 16 km (protect tendon; accept slightly lower endurance ceiling). Cite `achilles-tendinopathy-load`.

## R.3 Drop the 4th-run suggestion for this athlete (Achilles + routine conflict)

- **A-F5, C-F5:** suggesting a 4th run contradicts the Achilles limiter (more loading cycles) and the real routine (Mon/Fri strength, Wed volleyball, "missed workouts not compensated with volume"). **Remove the 4th-run path from v1.9.A.** When 3 slots cannot carry the required peak, lower `LONG_RUN_PEAK_KM` and emit the goal-reset `ChangeExplanation` (honest "complete strong, not peak"). A 4th run may only ever return gated behind `matheus_achilles_recent_max == 0` for ≥8 consecutive weeks (out of scope now).
- **Bruna under-stimulus path (C-F6, resolves v1.8.7 contradiction):** shared run defaults to the MORE CONSERVATIVE athlete's envelope (Matheus Achilles wins). If Bruna is chronically under-stimulated, the system suggests a Bruna-SOLO quality session on a non-shared slot — the ONLY divergence allowed in v1.9; full per-athlete macrocycle stays deferred. v1.8.7 updated to note this exception.

## R.4 DIV-1: phase-dependent quality cap must travel in the state

- **B-F2 (HIGH):** X.1 lets the phase override v1.7 `intensity_overreach` (cap 2 in `half_specific`), but `llm.py::_deterministic_guardrail_for_request` only passes `phase` as a pass-through string; `recommend_next_action` has no phase→cap logic. Fix: `AccumulatedState` carries `active_phase_quality_cap: int` (set by caller from `macrocycle.yaml`); `recommend_next_action` uses it instead of a hardcoded `>= 2`; it is serialized in `accumulated_state` so both call-sites apply the identical cap. Without this, the LLM envelope diverges from the pipeline (DIV-1 break).

## R.5 Make LLM prescriptions structured (kills fragile free-text parsing)

- **B-F4, X.6/G7:** add structured fields to `LlmRecommendationResponse`: `prescribed_pace_min_per_km: str | None`, `prescribed_distance_km: float | None`, `prescribed_intensity_label: str`. G7 validates these against recalibrated bands — no regex parsing of prose. If absent when a pace is implied, downgrade confidence + `request_manual_resolution`.
- **Binding template per slot (C-F1):** the engine's selected template ID per slot is a BINDING input to the LLM (`prescribed_template_id`). The LLM varies reps/structure/cues WITHIN it but cannot substitute a different template; `validate_llm_response` rejects mismatch. This is what stops the LLM smuggling periodization via "session design."
- **Tier-2 labeling enforceable (C-F2, B-F9):** add `general_training_knowledge: list[str]` to the response. Any citation pattern the prose lint detects must be in `science_refs` (Tier-1) OR `general_training_knowledge` (Tier-2 label); else rejected. A `suggested_science[].claim` substring may NOT appear in `next_workout`/`what_workout_showed` (no influencing a binding decision before human review).

## R.6 Determinism boundary stated explicitly (LLM is intentionally varied)

- **B-F8, C-F8:** determinism/snapshot tests apply ONLY to `build_athlete_state`, `recommend_next_action`, `derive_phase_schedule`, `plan_horizon`, pace recalibration, volume target. The LLM session-design prose is intentionally varied and is validated for envelope/band compliance, NOT output identity. Add this row to v1.9.B §B.1 and clarify v1.8.8 DoD #7.

## R.7 plan_horizon selection must be fully specified (no implementer guesswork)

- **B-F3:** add deterministic constants: `QUALITY_SLOT_PREFERENCE = ["thursday","tuesday"]` (Thursday preferred; Tuesday only if Thursday is post-volleyball recovery); `LONG_PROGRESSIVE_FREQUENCY = every 2nd Sunday in half_base, every Sunday in half_specific`; per-phase `template_rotation` ordered list. Snapshot-tested.
- **Pace bands serialized (B-F5):** `build_llm_request` reads `pace_bands.yaml` and includes them in the request; `validate_llm_response` checks against `request["pace_bands"]` (request-time bands), mirroring the `accumulated_state` pattern — no temporal skew when a race result updates bands mid-run.

## R.8 Cold-start consistency + readiness gate from real history

- **B-F6:** `consistency = completed/planned` over trailing 4 ISO weeks; when `planned_runs == 0` (before `plan_horizon` exists), `consistency = None` → gate `hold` with reason `insufficient_plan_history` (never divide-by-zero, never auto-advance). The pre-taper volume criterion is evaluated from `AccumulatedState` (actual history), not plan-matching.
- **Pre-taper dose raised (A-F6):** X.7 gate requires ≥4 (not ≥2) executed half-specific quality sessions — ensures the minimum effective dose was delivered, not just planned.

## R.9 Science correctness fixes

- **Riegel exponent (A-F3):** use `RIEGEL_EXPONENT = 1.08` (conservative for a recreational, Achilles-limited athlete); move toward 1.06 only after a completed 15+ km effort within 5% of prediction. The 8% one-step guard stays.
- **Taper duration (A-F4):** `TAPER_DAYS_A` becomes volume-scaled: ≤35 km/wk→14 d; 35–45→17 d; >45→21 d (default 17 for this profile). Aligns with `half_taper` 2–3 wk and Mujika/Bosquet.
- **Registry is blocking (A-F9, C-F7):** Step 0 of implementation — add X.9 refs to `science_refs.yaml` (`riegel-race-prediction`, `daniels-vdot-pacing`, `taper-performance-mujika`, `taper-meta-bosquet`, `half-marathon-prep-pfitzinger`) PLUS `heat-performance-decrement` (Périard et al. 2015, DOI 10.1007/s40279-015-0324-6); add `rule_refs.yaml` entries (`coaching-principle-deload`, `conservative-cold-start`, `long-run-progression`, `half-readiness-gate`, `garmin-outlier-filter`). No code citing a ref ships before its registry entry exists (S12).

## R.10 Heat handling reconciled with pace logic

- **C-F4, C-F10, F4:** `heat_flag: StrictBool = False` in the check-in YAML and `RecommendationInput` (distinct from the existing "heat" SYMPTOM term in `_classify_symptom_severity`, which is heat-illness → red flag). When `heat_flag` is high: G7 validates an EFFORT/PSE prescription (not pace); a race result with `conditions: heat` does NOT update pace bands (fail-closed: stale > poisoned) or applies a documented heat-adjustment. Cite `heat-performance-decrement`.

## R.11 Phase enum reconciliation

- **B-F8:** the `Phase` enum (`models.py`) has `TEN_K_POLISH`, `POST_TEN_K_RECOVERY`, `FIVE_TEN_K_DEVELOPMENT`, `HALF_BASE`, `HALF_SPECIFIC`, `HALF_TAPER`; the X.1 ladder uses `base`, `five_ten_k_sharpening`, etc. Reconcile by mapping X.1 to existing enum values where possible (the athlete is currently in `ten_k_polish`) and adding only the missing `base` phase. Decide in implementation; do not ship two naming systems.

## R.12 under_stimulus is informational only

- **C-F3:** `under_stimulus` NEVER raises the envelope or overrides a guardrail. It emits a `ChangeExplanation` (scope=periodization) recommending manual review / addressing the blocking signal (e.g., treat Achilles). DoD: with `under_stimulus` AND `achilles_trend_reduce` both active, action stays `reduce` (guardrail wins).

## R.13 Net effect on goal feasibility

With R.1–R.12 applied, the peak path is **feasible and honest**: long-run build spans all phases to ~18–20 km (or 16 km if Achilles forces it), weekly volume rises provably under the spike guardrail to a derived ~40 km peak (or a lowered, explained peak), a 17-day volume-scaled taper, conservative Riegel calibration, structured/bounded LLM prescriptions, and a pre-taper gate that requires the dose was actually delivered. Residual honest limits: 3x/week + Achilles caps the ceiling (the system says "complete strong" rather than overreaching), and full per-athlete macrocycle divergence stays deferred. These are stated to the athlete via `ChangeExplanation`, not hidden.


---

# Appendix C — External adversarial audit (Codex, read-only) + binding corrections

An independent agent (Codex CLI, read-only sandbox) reviewed the WHOLE spec against the real code, ran Python/grep to try to break it, and returned a "NOT safe/sufficient" verdict. Its strongest findings were INDEPENDENTLY RE-PROVEN here with simulation. The corrections below are **binding** and override any conflicting text above (including R.1/R.2/X.2). Where the spec previously asserted numbers, it now defers to a code-generated table.

## C.0 What the audit proved (re-verified with Python)

- **Long-run model was geometrically impossible (Codex #1, #2 — CONFIRMED).** Tying the long run to 50% of weekly volume while volume ramps under the load guardrail makes the long run DECAY to ~12 km, never 18–20 km. Simulation: from a real ~20 km/week base on 3 runs, the guardrail-safe peak weekly volume over 30 weeks is **~25 km/week** → long run **~12–14 km**. An 18–20 km long run is NOT safely reachable on 3 runs from this base. My earlier "feasible to 20 km" claim (X.2, R.13) was FALSE.
- **LLM containment is aspirational, not real (Codex #3 — CONFIRMED).** `validate_llm_response` today accepts `next_workout="10x400m at 5k pace based on Smith 2024 meta-analysis"` during `base`. The structured fields R.5 promises do not exist in `llm.py`.
- **Symptom classifier fails open (Codex #4 — CONFIRMED).** `"dor aguda no tendao"`, `"mancando"`, `"nao consegue apoiar"` → `mild` → `maintain`.
- **Self-consistency trap (Codex #10 — CONFIRMED, and it is the meta-lesson).** My 3–4 internal passes converged on shared vocabulary, not on an executable counterexample-resistant schedule. The external agent broke it in one Python run. **Rule going forward: any quantitative claim in this spec must be backed by a committed generator + golden table, not prose.**

## C.1 BINDING correction 1 — Honest goal & derived ceiling (replaces X.2 peak, R.1, R.2 volume math)

- **Delete every hardcoded peak** (`LONG_RUN_PEAK_KM = 20`, "~40 km/week peak"). Volume and long-run peak are **outputs of a generator**, never asserted.
- The generator computes the guardrail-safe ceiling from the athlete's REAL current baseline. For the current profile (~20 km/week, 3 runs, Achilles), the proven ceiling is **long ~12–14 km, week ~25 km** — NOT a half-specific 18–20 km.
- **Therefore the default goal for this athlete is explicitly "complete the half strong," not "peak."** The system states this to the athlete via `ChangeExplanation` at plan creation. Reaching a true 18–20 km long run requires one of three athlete-chosen paths, each with its cost surfaced:
  1. **Accept ~14–16 km long-run ceiling on 3 runs** → "complete strong" (default, safest).
  2. **Add a 4th easy run** → only path that reaches ~18 km safely; gated behind `achilles_recent_max == 0` for ≥8 consecutive weeks (deferred; conflicts with current Achilles status).
  3. **Extend the timeline / lower the race ambition.**
- The athlete picks; the system never silently pretends a 3-run/20 km base peaks at a strong half.

## C.2 BINDING correction 2 — One generator, one table, as the DoD (replaces all long-run/volume prose)

- Implement a single pure function `generate_volume_plan(baseline_km, achilles_state, weeks, phase_schedule) -> list[WeekPlan]` with ONE explicit state model: `last_build_peak`, `current_week_long`, `current_week_volume`, post-stepback resume = `min(prior_build_peak, rolling_mean * LOAD_RATIO_CAP)`.
- Invariants the function MUST satisfy, asserted by a golden test over the full horizon:
  - `weekly_load_spike` never fires against the actual rolling mean (already simulated: achievable).
  - `long <= SHARE * week` every week.
  - long-run peak and weekly peak equal the DERIVED ceiling, not a constant.
- **DoD = the committed generated table** (like the 24–30 week tables produced here), checked into the repo as a fixture. If the generator cannot produce a table meeting the goal, that is the signal to change the goal (C.1), not to fudge constants.
- Resolves Codex #1, #2 and the R.1 self-contradiction (the "+2 km cap" and "≥3 km long step" can never both hold — the long step is now DERIVED from the volume step, never independent).

## C.3 BINDING correction 3 — Separate "code today" from "to build" (Codex #8)

The spec must carry an explicit table: every symbol it references is tagged `EXISTS` (verified in `src/`) or `TO_BUILD`. `derive_phase_schedule`, `plan_horizon`, `AccumulatedState`, `ChangeExplanation`, `target_weekly_km`, `generate_volume_plan`, `active_phase_quality_cap`, `prescribed_*`, `heat_flag`, `weekly_load_spike`, `entered_taper_underprepared` are all **TO_BUILD**. No DoD may read as if a TO_BUILD symbol already constrains current behavior.

## C.4 BINDING correction 4 — Fail-closed safety is a blocking deliverable, not prose (Codex #3, #4, #6)

- **Symptom classifier:** ship the closed-world taxonomy with ASCII/PT-BR normalization and explicit injury-bearing phrase fixtures (`dor aguda`, `tendao`, `aquiles`, `mancando`, `nao consegue apoiar`, `pontada`) BEFORE any recommendation path is trusted; unknown non-benign text → `request_manual_resolution`. This is C1 promoted to blocking.
- **LLM containment:** the structured prescription fields + phase/template validation (R.5) are a HARD PREREQUISITE — until they exist, the LLM output is advisory only and MUST NOT alter the deterministic recommendation. State this explicitly so an implementer cannot wire the LLM in early.
- **Heat:** `heat_flag` is a NEW structured field distinct from the existing `"heat"` symptom term; ban the free-text overload.

## C.5 BINDING correction 5 — Canonical phase enum (Codex #7)

R.11 ("decide in implementation") is withdrawn. Canonical decision: KEEP the existing `Phase` enum (`TEN_K_POLISH`, `POST_TEN_K_RECOVERY`, `FIVE_TEN_K_DEVELOPMENT`, `HALF_BASE`, `HALF_SPECIFIC`, `HALF_TAPER`); add ONE value `BASE`. The X.1 ladder maps: `base→BASE`, `five_ten_k_sharpening→FIVE_TEN_K_DEVELOPMENT`, others unchanged. `ten_k_polish`/`post_ten_k_recovery` are pre-cycle states feeding into `BASE`. No second naming system ships.

## C.6 Process correction (Codex #10 — the important one)

Internal multi-pass review by the SAME author class converges on vocabulary, not truth. **Every future quantitative or safety claim in this spec is invalid until a committed script reproduces it and a golden fixture pins it.** The external read-only adversarial pass (`codex exec -s read-only`) is added as a REQUIRED gate before the spec is handed off — not optional.

## C.7 Net status after Appendix C

The architecture (deterministic spine, DIV-1, explainability, append-only, fail-closed intent) remains sound and is the genuine value. But the spec is **NOT yet implementer-ready**. Blocking items, in order:
1. Replace long-run/volume prose with `generate_volume_plan` + committed golden table; adopt the honest derived ceiling and "complete strong" default (C.1, C.2).
2. Ship fail-closed safety inputs (symptom taxonomy, Achilles accumulated state, heat field, missing-data behavior) and keep the LLM advisory until containment fields exist (C.4).
3. Tag every symbol EXISTS/TO_BUILD and fix the phase enum (C.3, C.5).

Only after 1–3 is the spec safe to hand to Codex for implementation. The honest headline for the athlete: on 3 runs/week with an Achilles limiter, this system will coach you safely and adaptively to **complete a strong half** — a true competitive peak would require a 4th run (Achilles permitting) or a longer runway, and the system will say so explicitly rather than pretend.

## D. v2.0 — Pacing calibration, race-via-UI, and full-cycle proof (shipped)

This section records the v2.0 increment (all reproduced by committed scripts + golden tests, each Codex-reviewed read-only).

### D.1 Race-calibrated pacing (`pacing.py`)
- `Benchmark(distance_km, time_seconds, conditions)` + `zones_from_benchmark` derive PT-BR pace zones from a real race via Riegel (exponent 1.08). Zones are **anchored on measured race pace**, not generic VDOT offsets, to fit an endurance profile (easy sits near race pace). Bruna's 5K (29:10) → easy 6:40, limiar/HMP 6:10, tiros 5:50, projeção meia 6:33 — verified against her demonstrated paces.
- `select_best` picks the strongest recent effort (fastest normalized to 5K); zones **auto-tighten** as fitness improves, never loosen on easy days.
- `classify_effort` auto-detects a strong effort (race/threshold) from pace-vs-zone + PSE. **Binding safety rule (Codex):** auto-calibration requires `PSE>=7` AND `category!=easy` AND Bruna-evidence (`shared_run+bruna_present`) — a fast downhill/GPS-glitch easy run can NEVER tighten zones (injury risk). Stale (>120d) and <5km efforts are excluded.
- `heat_adjusted_pace`: +3s/km per °C above 15°C (cap +90s); heat conditions switch prescriptions to effort/PSE.

### D.2 Race entry via UI (no repo edits)
- `RaceIntake` model + `_write_race` (append-only to `races.yaml`, dedup by `race_id = {dist}k-{date}`). `process_frontend_intake` writes it; the Operar tab has a race form (`buildRaceIntakePayload`/`validateRaceForm`). The operational workflow handles a Garmin-less race intake (runs `build_plan.py`, commits `data/plan`). A submitted race recalibrates zones automatically.

### D.3 Full-cycle harness + taper fix
- `scripts/sim_harness.py::run_cycle(feedback)` drives the REAL engine week-by-week to the Jan race. It feeds **action-adjusted executed load** back into history (off=0, easy=0.5×, reduce=0.7× of the planned long), so interruptions genuinely lower future load (Codex faithfulness fix — proven: perfect=467km vs U-inverted=326km executed long total).
- **Harness-exposed periodization bug (fixed):** `generate_volume_plan` was blind to the taper phase, so the final week could return to peak. `select_week_sessions` now caps the `HALF_TAPER` long run to `TAPER_LONG_FRACTION=0.55` of peak.

### D.4 26 scenarios locked (`tests/test_full_cycle_scenarios.py`)
26 edge-case cycles (V, inverted-U, perfect, weeks off, Achilles injury+recovery, sustained illness, red flag, chronic poor sleep, heavy volleyball, tune-up race, taper injury, etc.) run through the real engine. Invariants asserted: full cycle reached (specific+taper present), long-run progression, taper reduces below peak, red_flag → off/easy (never maintain), PSE≥9 → pullback then resume, Achilles≥5 → `bruna_without_matheus` (the Achilles limits Matheus, not Bruna). **Non-vacuous (Codex):** each safety scenario asserts its intended trigger actually fires. Plus a readiness summary (`boa/cautela/recuperar/indefinido`, fail-closed) and weekly narrative recap.

Net: race calibration + concrete per-session pace + a living plan that auto-refreshes and tapers correctly, proven adaptive across 26 cycles. 330 Python tests + 24 Playwright e2e + frontend build green.
