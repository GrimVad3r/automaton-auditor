# Automaton Auditor — Evidence-Backed Executive Summary (Draft Replacement)

**Date:** 2026-02-28  
**Repository:** https://github.com/GrimVad3r/automaton-auditor  
**Primary Model:** mistralai/ministral-3-14b-reasoning via LM Studio (`OPENAI_BASE_URL=http://127.0.0.1:1234/v1`, JSON mode)

---

## What the System Actually Implements

- **Parallel Orchestration (Detectives & Judges)**  
  Defined in `src/core/graph.py`: initialize → `repo_investigator` & `doc_analyst` (fan-out), aggregate_evidence → `prosecutor`, `defense`, `tech_lead` (fan-out), unified `handle_error` → `chief_justice` → finalize.

- **Sandboxed Git Operations (No `os.system`)**  
  `src/tools/git_tools.py` uses `RepositorySandbox.clone_repository`; evidence emitted as `sandboxed_git_clone`. No raw `os.system` calls in git operations.

- **Structured JSON Enforcement**  
  `src/agents/judges/base_judge.py`: opinions must match `StructuredOpinion` (criterion_id, score, argument ≥100 chars, cited_evidence list). `force_json_mode` is enabled for local LM Studio endpoints to avoid tool-calling errors.

- **Distinct Judge Personas**  
  Persona prompts live in:  
  - Prosecutor: `src/agents/judges/prosecutor.py` (marker: “Trust No One”)  
  - Defense: `src/agents/judges/defense.py` (marker: “Reward Effort”)  
  - Tech Lead: `src/agents/judges/tech_lead.py` (marker: “Does it actually work”)  
  RepoInvestigator emits evidence proving these prompt distinctions.

- **Chief Justice Synthesis**  
  `src/agents/justice/chief_justice.py` performs weighted aggregation with variance handling and security caps.

- **Vision Inspector (Status)**  
  `ENABLE_VISION_INSPECTOR` is **false by default**; VisionInspector remains experimental/stubbed.

### Graph Flow (fan-out + fan-in)

```mermaid
flowchart TD
    Start([START]) --> Init[Initialize]

    Init -->|fan-out| Repo[RepoInvestigator\n(sandboxed git)]
    Init -->|fan-out| Doc[DocAnalyst\n(PDF)]
    Init -->|optional fan-out| Vision[VisionInspector\n(disabled by default)]

    Repo --> Agg[Aggregate Evidence]
    Doc --> Agg
    Vision --> Agg

    Agg -->|fan-out| Pros[Prosecutor\n(Trust No One)]
    Agg -->|fan-out| Def[Defense\n(Reward Effort)]
    Agg -->|fan-out| Tech[Tech Lead\n(Does it actually work)]

    Pros --> Err[Handle Error\n(fan-in)]
    Def --> Err
    Tech --> Err

    Err --> CJ[Chief Justice\n(weighted synthesis + caps)]
    CJ --> Finalize[Finalize + Report]
    Finalize --> End([END])

    subgraph Enforcement
      Pros -.-> SO1[StructuredOpinion JSON]
      Def  -.-> SO2[StructuredOpinion JSON]
      Tech -.-> SO3[StructuredOpinion JSON]
    end
```

---

## Current Posture (Truthful Claims)

- **Architecture:** Production-like parallel LangGraph with centralized error collection; conditional fail-fast toggle (`AUDITOR_FAIL_FAST`).  
- **Security:** Git cloning is sandboxed; AST tools flag `os.system` if present elsewhere.  
- **Structured Outputs:** All judges coerce to `StructuredOpinion`; non-compliant outputs are grounded and score-capped.  
- **Personas:** Three distinct system prompts are present and referenced in evidence context.  
- **Model Stack:** Mistral 3 14B reasoning via LM Studio, JSON-only prompts to avoid function-call incompatibility.

---

## Items Not Yet Implemented (Be explicit)

- Vision-based UI audit is **not** active by default; claims should say “planned/experimental,” not “production-ready.”  
- No explicit graph edges for “Evidence Missing”/“Node Failure” recovery beyond `handle_error`; conditional paths could be added.  
- Dialectical synthesis is represented by parallel judges + Chief Justice, but no multi-turn persona debate transcript is stored.

---

## Evidence References (tie every claim to code)

- Parallel fan-out & handle_error: `src/core/graph.py`  
- Sandboxed git: `src/tools/git_tools.py`  
- StructuredOpinion & JSON mode: `src/agents/judges/base_judge.py`  
- Personas: `src/agents/judges/prosecutor.py`, `defense.py`, `tech_lead.py`  
- Typed states & outputs: `src/core/state.py`

---

## Recommended Next Increments

1. Add explicit conditional edges for “evidence missing / node failure” in `graph.py` (removes Prosecutor’s orchestration gap).  
2. Persist a short persona-differentiation evidence item per run (already emitted; ensure it’s injected into judge context).  
3. If desired, turn on VisionInspector and document it truthfully, or remove the “Vision Beta” claim from the PDF.

---

## Honest Score Guidance (expected after alignment)

- forensic_accuracy_code: 4/5 once sandbox evidence is cited.  
- forensic_accuracy_docs: 4/5 once parallel-graph evidence is explicitly cited in the doc.  
- judicial_nuance: 4/5 once persona-prompt evidence and StructuredOpinion enforcement are cited.
