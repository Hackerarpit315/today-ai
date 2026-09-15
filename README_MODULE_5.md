# Today AI — Module 5: Verification Engine

## 1. What Module 5 does

Module 5 evaluates research results that are explicitly supplied to it. It compares factual-looking statements across those results and reports agreement, conflicts, insufficient evidence, and a deterministic confidence score.

It does **not** perform research or establish absolute real-world truth.

## 2. Why verification is separate from research

Module 4 is responsible for finding and ranking relevant supplied sources. Module 5 has a different responsibility: checking whether the supplied evidence is internally consistent. Keeping the responsibilities separate makes each component easier to test and later integrate.

## 3. Input schema

`VerificationRequest` contains:

- `request_id`: UUID
- `query`: non-empty string
- `research_results`: list of `VerificationResearchResult`

Each research result contains:

- `source_id`
- `title`
- `content`
- `source_type`
- `relevance_score` from `0` to `1`

Pydantic uses `ConfigDict(extra="forbid")`, so unexpected fields are rejected.

## 4. Output schema

`VerificationResponse` contains:

- `request_id`
- `verified`
- `conflict_detected`
- `verification_status`
- `verified_claims`
- `conflicting_claims`
- `insufficient_claims`
- `supporting_sources`
- `conflicting_sources`
- `confidence`

Status values are `verified`, `conflicting`, `insufficient_evidence`, and `unverified`.

## 5. Verification algorithm

The implementation is deterministic and local:

1. Ignore results whose `relevance_score` is `0`.
2. Split source content into simple statements.
3. Normalize and tokenize text.
4. Ignore very short tokens and common stop words.
5. Extract simple factual values such as dates, numbers, percentages, and URLs.
6. Build a normalized claim key from the remaining meaningful terms.
7. Group claims by that key.
8. Treat identical values from multiple sources as agreement.
9. Treat different values for the same claim key as a conflict.
10. Claims that have only one supporting source are treated as insufficient evidence.

## 6. Conflict detection

Conflict detection is intentionally conservative and deterministic. For example, statements with the same normalized claim subject but different dates or numbers can be identified as conflicting.

Equivalent wording can still agree when their extracted factual values normalize to the same value.

## 7. Confidence calculation

Confidence is an explainable score, not a probability of truth. Agreement between multiple relevant sources increases the score. Conflicts and insufficient evidence reduce it. The result is always bounded between `0` and `1`.

Two sources repeating the same incorrect information can therefore still produce `verified=True`; that means the supplied evidence is internally consistent, not that the fact is guaranteed to be true in the real world.

## 8. Limitations

This first deterministic implementation does not understand language semantically. It may miss paraphrases that do not expose comparable factual values, and it can group unrelated statements if their normalized claim terms happen to be similar. It is intentionally limited so that later verification improvements can be added without introducing an LLM.

## 9. Why external access is disabled

Module 5 does not use web search, Google, Bing, HTTP requests, browsers, n8n, OpenAI/LLM services, databases, Supabase, or other external APIs. Only explicitly supplied research results are evaluated.

## 10. Running tests

From the Today AI project directory:

```text
.\\.venv\\Scripts\\python.exe -m pytest -q tests/test_verification.py
```

The tests use a standalone FastAPI application containing only the Module 5 router and do not start `app.main`.
