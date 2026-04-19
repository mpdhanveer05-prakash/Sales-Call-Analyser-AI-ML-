# Disposition Taxonomy — 18 Categories

Used by the LLM (Ollama `llama3.1:8b`) to classify the outcome of each call.
Stored as `calls.disposition`. Displayed via `DispositionBadge` component in the frontend.

---

## Positive Outcomes

| Code | Label | Description | LLM Signals |
|---|---|---|---|
| CONVERTED | Converted | Prospect agreed to buy | "yes", "sign me up", payment discussion, explicit agreement |
| INTERESTED_FOLLOWUP | Interested — Follow-up Booked | Positive, next step scheduled | Date/time agreed for follow-up, prospect engaged |
| INTERESTED_NO_NEXTSTEP | Interested — No Next Step | Warm but no commitment made | Positive tone, no date agreed, "I'll think about it" |

## Objection Outcomes

| Code | Label | Description | LLM Signals |
|---|---|---|---|
| OBJECTION_PRICE | Objection: Price | Concerned about cost | "too expensive", "can't afford", price comparison |
| OBJECTION_TIMING | Objection: Timing | Not the right time | "not now", "maybe next quarter", "busy right now" |
| OBJECTION_AUTHORITY | Objection: Authority | Needs to check with others | "need to ask my partner/boss", "not my decision" |
| OBJECTION_NEED | Objection: Need | Does not see the value | "don't need it", "already have something", no pain point |
| OBJECTION_COMPETITOR | Objection: Competitor | Evaluating a competing product | competitor name mentioned, "already talking to X" |

## Negative Outcomes

| Code | Label | Description | LLM Signals |
|---|---|---|---|
| NOT_INTERESTED | Not Interested | Flat rejection | "not interested", "remove me", "stop calling" |
| CALLBACK_REQUESTED | Callback Requested | Asked to be called back at a later time | "call me back", specific future time mentioned |
| DNC | Do Not Call | Prospect requested no further contact | "don't call again", legal DNC request |

## No-Contact Outcomes

| Code | Label | Description | LLM Signals |
|---|---|---|---|
| VOICEMAIL | Voicemail | Left a voicemail message | Agent speaking to voicemail, beep heard |
| NO_ANSWER | No Answer | Nobody picked up | Ringing with no response, auto-disconnect |
| WRONG_NUMBER | Wrong Number | Incorrect contact reached | "wrong number", name mismatch, confused party |
| GATEKEEPER | Gatekeeper | Did not reach the decision maker | Receptionist, assistant blocking decision maker |

## Special Cases

| Code | Label | Description | LLM Signals |
|---|---|---|---|
| PARTIAL_CALL | Partial Call | Call dropped or cut short | Abrupt end, disconnection mid-conversation |
| LANGUAGE_BARRIER | Language Barrier | Communication was not possible | Unable to understand each other |
| OTHER | Other | Does not fit any other category | Use only when no other code fits |

---

## LLM Prompt Guidance

The disposition prompt instructs the LLM to:
1. Read the full transcript with speaker labels
2. Select **exactly one** code from the list above
3. Return only the code string (no explanation) so it can be parsed directly

Re-prompting occurs if the output is not a valid code from the taxonomy.

---

## Usage in Code

- **Backend classification**: `backend/app/services/ollama_service.py` → `classify_disposition()`
- **Database column**: `calls.disposition` (VARCHAR, nullable until COMPLETED)
- **API response**: included in `CallOut` schema
- **Frontend display**: `frontend/src/components/calls/DispositionBadge.tsx`
