"""
RAG Evaluation — two separate diagnostic layers:

Layer 1 — Retrieval quality (Recall@k):
  For each GT record, check if the gold chunk appears in top-k retrieved results.
  Measured independently of the LLM generator.

Layer 2 — End-to-end answer quality:
  Run full agent pipeline; score answer against gold using exact match + LLM judge.

This separation is the key diagnostic: if Recall@k is low, fix retrieval.
If Recall@k is high but answer quality is low, the generator (LLM) is the bottleneck.
"""
import json
import re
from dataclasses import dataclass, field, asdict
from typing import Optional

from app.kb.retriever import retrieve


# ── Data structures ────────────────────────────────────────────────────────────
@dataclass
class GTRecord:
    """One ground-truth evaluation record."""
    id:           str
    query:        str
    gold_answer:  str
    gold_chunks:  list[str]   # key phrases that must appear in retrieved chunks
    workflow:     str = "sales"
    api:          str = ""
    difficulty:   str = "medium"  # easy | medium | hard


@dataclass
class RetrievalResult:
    record_id:    str
    query:        str
    hit_at_1:     bool = False
    hit_at_2:     bool = False
    hit_at_4:     bool = False
    retrieved:    list[str] = field(default_factory=list)
    gold_chunks:  list[str] = field(default_factory=list)


@dataclass
class AnswerResult:
    record_id:      str
    query:          str
    gold_answer:    str
    agent_answer:   str
    exact_match:    bool  = False
    keyword_match:  float = 0.0   # fraction of gold keywords found in answer
    llm_score:      Optional[float] = None  # 0–1 from LLM judge (if available)
    citations_ok:   bool  = False  # answer contains at least one [KB-N] citation


@dataclass
class EvalReport:
    total:              int   = 0
    recall_at_1:        float = 0.0
    recall_at_2:        float = 0.0
    recall_at_4:        float = 0.0
    avg_keyword_match:  float = 0.0
    avg_llm_score:      float = 0.0
    citation_rate:      float = 0.0
    retrieval_results:  list  = field(default_factory=list)
    answer_results:     list  = field(default_factory=list)
    diagnosis:          str   = ""


# ── Retrieval evaluation (Layer 1) ────────────────────────────────────────────
def _chunk_hit(retrieved_chunks: list[dict], gold_phrases: list[str]) -> bool:
    """Return True if ANY gold phrase appears in ANY retrieved chunk."""
    combined = " ".join(r["content"].lower() for r in retrieved_chunks)
    return any(phrase.lower() in combined for phrase in gold_phrases)


def evaluate_retrieval(records: list[GTRecord], k: int = 4) -> list[RetrievalResult]:
    results = []
    for rec in records:
        top4 = retrieve(rec.query, k=k)
        top2 = top4[:2]
        top1 = top4[:1]
        results.append(RetrievalResult(
            record_id=rec.id,
            query=rec.query,
            hit_at_1=_chunk_hit(top1, rec.gold_chunks),
            hit_at_2=_chunk_hit(top2, rec.gold_chunks),
            hit_at_4=_chunk_hit(top4, rec.gold_chunks),
            retrieved=[r["content"][:120] for r in top4],
            gold_chunks=rec.gold_chunks,
        ))
    return results


# ── Answer evaluation (Layer 2) ───────────────────────────────────────────────
def _keyword_match(gold: str, answer: str) -> float:
    """Fraction of significant gold keywords found in answer."""
    stopwords = {"the", "a", "an", "is", "are", "was", "were", "to", "of",
                 "and", "or", "in", "on", "at", "for", "with", "this", "that"}
    gold_words = [w.lower() for w in re.findall(r"\w+", gold) if w.lower() not in stopwords]
    if not gold_words:
        return 0.0
    hits = sum(1 for w in gold_words if w in answer.lower())
    return round(hits / len(gold_words), 3)


def _has_citation(answer: str) -> bool:
    return bool(re.search(r"\[KB-\d+\]", answer))


def _llm_judge(query: str, gold: str, answer: str) -> Optional[float]:
    """Score answer 0–1 using LLM judge. Returns None if LLM unavailable."""
    try:
        from app.llm import get_llm
        from langchain.schema import SystemMessage, HumanMessage
        llm = get_llm(temperature=0)
        prompt = (
            f"Query: {query}\n"
            f"Gold answer: {gold}\n"
            f"Agent answer: {answer}\n\n"
            "Score the agent answer from 0.0 to 1.0 based on factual correctness "
            "and completeness compared to the gold answer. "
            "Reply with ONLY a number between 0.0 and 1.0."
        )
        resp = llm.invoke([SystemMessage(content="You are an answer quality judge."),
                           HumanMessage(content=prompt)])
        return float(re.search(r"[\d.]+", resp.content).group())
    except Exception:
        return None


def evaluate_answers(
    records: list[GTRecord],
    agent_answers: list[str],
    use_llm_judge: bool = False,
) -> list[AnswerResult]:
    results = []
    for rec, answer in zip(records, agent_answers):
        km = _keyword_match(rec.gold_answer, answer)
        llm_score = _llm_judge(rec.query, rec.gold_answer, answer) if use_llm_judge else None
        results.append(AnswerResult(
            record_id=rec.id,
            query=rec.query,
            gold_answer=rec.gold_answer,
            agent_answer=answer,
            exact_match=rec.gold_answer.strip().lower() in answer.strip().lower(),
            keyword_match=km,
            llm_score=llm_score,
            citations_ok=_has_citation(answer),
        ))
    return results


# ── Aggregate report ──────────────────────────────────────────────────────────
def build_report(
    retrieval_results: list[RetrievalResult],
    answer_results: list[AnswerResult],
) -> EvalReport:
    n = len(retrieval_results)
    if n == 0:
        return EvalReport()

    r1 = sum(r.hit_at_1 for r in retrieval_results) / n
    r2 = sum(r.hit_at_2 for r in retrieval_results) / n
    r4 = sum(r.hit_at_4 for r in retrieval_results) / n

    avg_km = sum(a.keyword_match for a in answer_results) / max(len(answer_results), 1)
    llm_scores = [a.llm_score for a in answer_results if a.llm_score is not None]
    avg_llm = sum(llm_scores) / len(llm_scores) if llm_scores else 0.0
    cit_rate = sum(a.citations_ok for a in answer_results) / max(len(answer_results), 1)

    # Diagnosis
    if r4 < 0.7:
        diagnosis = "RETRIEVAL_BOTTLENECK: Recall@4 below 0.70 — improve chunking or add more corpus documents."
    elif r4 >= 0.7 and avg_km < 0.5:
        diagnosis = "GENERATOR_BOTTLENECK: Recall@4 is good but answer keyword match is low — LLM is not using retrieved chunks effectively."
    elif cit_rate < 0.8:
        diagnosis = "CITATION_GAP: Answers lack [KB-N] citations — enforce citation requirement in Executor prompt."
    else:
        diagnosis = "OK: Retrieval and answer quality both acceptable."

    return EvalReport(
        total=n,
        recall_at_1=round(r1, 3),
        recall_at_2=round(r2, 3),
        recall_at_4=round(r4, 3),
        avg_keyword_match=round(avg_km, 3),
        avg_llm_score=round(avg_llm, 3),
        citation_rate=round(cit_rate, 3),
        retrieval_results=[asdict(r) for r in retrieval_results],
        answer_results=[asdict(a) for a in answer_results],
        diagnosis=diagnosis,
    )


# ── Built-in GT records (from GT sheet — all 4 APIs, sales + support) ─────────
BUILTIN_GT_RECORDS: list[GTRecord] = [
    # ── Directions API — Sales ──────────────────────────────────────────────
    GTRecord("dir-s-01", "Compare Directions API providers on pricing for 100K requests/month in Europe with real-time traffic",
             "Standard plan $299/month includes 500K requests. Real-time traffic available in 85 countries including Europe.",
             ["$299", "500K", "85 countries", "real-time traffic"], "sales", "directions", "easy"),
    GTRecord("dir-s-02", "What is the maximum number of waypoints supported per Directions API request?",
             "Standard and Professional plans support up to 23 waypoints. Enterprise supports up to 150 waypoints.",
             ["23 waypoints", "150 waypoints", "Enterprise"], "sales", "directions", "easy"),
    GTRecord("dir-s-03", "Does the Directions API support truck routing with height and weight constraints?",
             "Truck routing with height, weight, width, and length constraints is available on Professional and Enterprise plans.",
             ["truck", "height", "weight", "Professional", "Enterprise"], "sales", "directions", "medium"),
    GTRecord("dir-s-04", "Which provider has the most waypoints per request for Directions API?",
             "Our service supports 23 waypoints on Standard/Professional and 150 on Enterprise. Provider B supports 25 on all plans. Provider C supports 10 on Starter and 50 on Business.",
             ["23", "150", "Provider B", "25", "Provider C"], "sales", "directions", "medium"),
    GTRecord("dir-s-05", "What are the overage charges for Directions API on the Standard plan?",
             "Overage on Standard plan is $0.005 per request beyond the 500K monthly included requests.",
             ["$0.005", "overage", "500K"], "sales", "directions", "easy"),

    # ── Directions API — Support ────────────────────────────────────────────
    GTRecord("dir-sup-01", "Getting 422 error on Directions API, what parameter is missing?",
             "422 MISSING_PARAMETER means a required field is absent. Check the required_fields array in the error response body. Required parameters are origin, destination, and mode.",
             ["422", "MISSING_PARAMETER", "required_fields", "origin", "destination", "mode"], "support", "directions", "easy"),
    GTRecord("dir-sup-02", "Directions API returns ZERO_RESULTS for some routes in rural Germany",
             "ZERO_RESULTS means no route was found. This can occur in areas with limited road data. Try removing avoid parameters or using a different mode.",
             ["ZERO_RESULTS", "route", "avoid", "mode"], "support", "directions", "medium"),
    GTRecord("dir-sup-03", "Traffic duration not returned in Directions API response",
             "Traffic-adjusted duration requires the departure_time parameter to be set in ISO8601 format. Without departure_time, only static duration is returned.",
             ["departure_time", "ISO8601", "traffic", "duration_in_traffic_s"], "support", "directions", "easy"),

    # ── Distance Matrix API — Sales ─────────────────────────────────────────
    GTRecord("dm-s-01", "Compare Distance Matrix API limits across providers for 500 origins x 500 destinations",
             "Our Standard supports 25x25=625 elements, Professional 50x50=2500, Enterprise 100x100=10000 with async batch up to 1000x1000. Provider B max is 10x10. Provider C max is 50x50 on Enterprise.",
             ["25x25", "50x50", "100x100", "async batch", "1000x1000"], "sales", "distance_matrix", "hard"),
    GTRecord("dm-s-02", "How many Distance Matrix API requests do I need for 200 origins x 200 destinations on Professional plan?",
             "Professional plan limit is 50x50 per request. For 200x200: ceil(200/50) x ceil(200/50) = 4 x 4 = 16 requests.",
             ["50x50", "16 requests", "ceil", "Professional"], "sales", "distance_matrix", "hard"),
    GTRecord("dm-s-03", "What is the pricing for Distance Matrix API on Professional plan?",
             "Professional plan is $999/month including up to 5M elements/month. Overage is $0.002 per element.",
             ["$999", "5M elements", "$0.002", "overage"], "sales", "distance_matrix", "easy"),
    GTRecord("dm-s-04", "Does Distance Matrix API support async batch processing for large matrices?",
             "Yes. POST /v1/matrix/batch supports async jobs up to 1000x1000 on Enterprise. Returns job_id; poll GET /v1/matrix/batch/{job_id} for status.",
             ["async", "batch", "1000x1000", "job_id", "Enterprise"], "sales", "distance_matrix", "medium"),

    # ── Distance Matrix API — Support ───────────────────────────────────────
    GTRecord("dm-sup-01", "Distance Matrix API returning 400 MATRIX_TOO_LARGE",
             "400 MATRIX_TOO_LARGE means the origins x destinations count exceeds your plan limit. Standard: 25x25, Professional: 50x50, Enterprise: 100x100. Reduce matrix size or use async batch endpoint.",
             ["MATRIX_TOO_LARGE", "25x25", "50x50", "100x100", "async batch"], "support", "distance_matrix", "medium"),
    GTRecord("dm-sup-02", "Some Distance Matrix elements return NOT_FOUND status",
             "NOT_FOUND at element level means that specific origin-destination pair has no routable path. Verify coordinates are valid and in a routable area. Check coordinate order: lat before lon.",
             ["NOT_FOUND", "routable", "coordinates", "lat", "lon"], "support", "distance_matrix", "medium"),

    # ── Autocomplete API — Sales ────────────────────────────────────────────
    GTRecord("ac-s-01", "Compare Autocomplete API coverage across providers",
             "Our service covers 195 countries with POI in 85. Provider B covers 180 countries with POI in 60. Provider C covers 150 countries with POI in 40.",
             ["195 countries", "85", "Provider B", "180", "Provider C", "150"], "sales", "autocomplete", "medium"),
    GTRecord("ac-s-02", "How do session tokens reduce Autocomplete API billing?",
             "Session tokens group all autocomplete keystrokes plus one place detail call into a single billable session, regardless of how many keystrokes the user types.",
             ["session_token", "billable session", "keystrokes", "place detail"], "sales", "autocomplete", "medium"),
    GTRecord("ac-s-03", "What is the minimum query length for Autocomplete API?",
             "The q parameter must be at least 2 characters. Shorter queries return empty results.",
             ["2 characters", "minimum", "q parameter"], "sales", "autocomplete", "easy"),

    # ── Autocomplete API — Support ──────────────────────────────────────────
    GTRecord("ac-sup-01", "Autocomplete returns no results for rural addresses in Germany",
             "Rural address coverage varies by country. Try removing the country filter, reducing query specificity, or checking if the address exists in a less specific form.",
             ["rural", "country filter", "specificity", "coverage"], "support", "autocomplete", "medium"),
    GTRecord("ac-sup-02", "Autocomplete suggestions not biased to user location",
             "Location bias requires lat, lon, and radius_m parameters. Confirm device GPS coordinates are being passed and radius_m is set to a reasonable value such as 50000 metres.",
             ["lat", "lon", "radius_m", "location bias", "GPS"], "support", "autocomplete", "easy"),

    # ── Reverse Geocode API — Sales ─────────────────────────────────────────
    GTRecord("rg-s-01", "Compare Reverse Geocode API batch limits across providers",
             "Our service supports batch up to 1000 coordinates on Professional and Enterprise. Provider B does not support batch. Provider C supports batch up to 500 on Enterprise only.",
             ["1000", "batch", "Professional", "Provider B", "Provider C", "500"], "sales", "reverse_geocode", "medium"),
    GTRecord("rg-s-02", "What coordinate precision is needed for street-level reverse geocoding?",
             "Use at least 4 decimal places for street-level accuracy (±11m precision). 6 decimal places recommended for ±0.11m precision.",
             ["4 decimal places", "6 decimal places", "street-level", "precision"], "sales", "reverse_geocode", "easy"),

    # ── Reverse Geocode API — Support ───────────────────────────────────────
    GTRecord("rg-sup-01", "Reverse Geocode returning APPROXIMATE results instead of street address",
             "APPROXIMATE means the area has limited street-level data. This is common in rural areas. The result is the geometric centre of the known area rather than a specific address.",
             ["APPROXIMATE", "rural", "street-level", "geometric centre"], "support", "reverse_geocode", "medium"),
    GTRecord("rg-sup-02", "Reverse Geocode returning wrong country for coordinates near border",
             "Verify coordinate order is lat before lon. A common mistake is passing lon before lat which places the point in a completely different location.",
             ["coordinate order", "lat before lon", "lon before lat"], "support", "reverse_geocode", "easy"),

    # ── Cross-API — Escalation ──────────────────────────────────────────────
    GTRecord("esc-01", "Error rate above 10% on location API for 3 hours affecting 200 vehicles",
             "Error rate >5% sustained >15 minutes requires immediate L2 escalation. Provide case_id, affected_service, error_codes, steps_taken, and impact_assessment.",
             ["L2 escalation", "5%", "15 minutes", "case_id", "impact_assessment"], "support", "tracking", "hard"),
    GTRecord("esc-02", "Customer needs sub-metre accuracy and 15000 concurrent devices",
             "Sub-metre accuracy requires UWB evaluation — escalate to Solutions Engineer. More than 10000 concurrent devices also triggers Solutions Engineer escalation.",
             ["Solutions Engineer", "UWB", "10000 devices", "sub-metre"], "sales", "tracking", "hard"),
]


# ── Run full evaluation ────────────────────────────────────────────────────────
def run_retrieval_eval(records: Optional[list[GTRecord]] = None, k: int = 4) -> EvalReport:
    """Run retrieval-only evaluation (Layer 1). No LLM calls."""
    if records is None:
        records = BUILTIN_GT_RECORDS
    retrieval_results = evaluate_retrieval(records, k=k)
    return build_report(retrieval_results, [])


def run_full_eval(
    records: Optional[list[GTRecord]] = None,
    use_llm_judge: bool = False,
) -> EvalReport:
    """Run full evaluation: retrieval + agent answers (Layer 1 + Layer 2)."""
    from app.agents.orchestrator import run_workflow
    if records is None:
        records = BUILTIN_GT_RECORDS

    retrieval_results = evaluate_retrieval(records, k=4)

    agent_answers = []
    for rec in records:
        try:
            result = run_workflow(f"eval-{rec.id}", rec.workflow, rec.query, None)
            agent_answers.append(result.get("response", ""))
        except Exception:
            agent_answers.append("")

    answer_results = evaluate_answers(records, agent_answers, use_llm_judge=use_llm_judge)
    return build_report(retrieval_results, answer_results)
