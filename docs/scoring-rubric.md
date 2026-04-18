# Scoring Rubric — Sales Call Analyzer

---

## Layer 1: Speech Quality Score (0–100)

Automated from audio signal and AGENT transcript. No LLM required.
Computed by `ml-service/app/routes/speech_analysis.py` → scored by `backend/app/services/speech_scoring_service.py`.

### Dimension Weights

| Dimension | Weight | Tool | Raw Metric |
|---|---|---|---|
| Pronunciation | 15% | faster-whisper confidence | avg word confidence (0–1) |
| Intonation | 15% | praat-parselmouth | F0 standard deviation (Hz) |
| Fluency | 15% | librosa RMS silence detection | Pauses per minute |
| Grammar | 15% | LanguageTool `/v2/check` | Grammar errors per 100 words |
| Vocabulary | 10% | spaCy lemmatisation | Type-token ratio (content words) |
| Pace | 10% | Transcript timestamps | Words per minute (WPM) |
| Clarity | 10% | faster-whisper confidence | % words with confidence < 0.6 |
| Filler Words | 10% | Regex on AGENT transcript | Filler words per minute |

### Per-Dimension Thresholds

#### Pronunciation
`score = avg_word_confidence × 100`

#### Intonation (F0 Std Dev in Hz)
| Range | Score |
|---|---|
| < 5 Hz (monotone) | 20 |
| 5–20 Hz | 20–80 (linear) |
| 20–80 Hz (natural) | 100 |
| > 80 Hz (too varied) | Decreasing 1.5/Hz |

#### Fluency (Pauses per Minute, min silence = 0.3s)
| Pauses/min | Score |
|---|---|
| < 1 | 60 |
| 1–3 | 60–100 (linear) |
| 3–8 (natural pacing) | 100 |
| > 8 (choppy) | Decreasing 7/pause |

#### Grammar
`score = max(0, 100 − errors_per_100_words × 8.33)`
- 0 errors → 100 · 12+ errors/100w → 0
- Excludes style and typographical issues (grammar only)

#### Vocabulary (Type-Token Ratio on content words)
`score = min(100, TTR × 200)`
- TTR 0.5+ → 100 · 0.25 → 50

#### Pace (Words per Minute — AGENT only)
| WPM | Score |
|---|---|
| < 80 | 0 |
| 80–120 | 60–100 (linear) |
| 120–160 (ideal for sales) | 100 |
| 160–200 | Decreasing |
| > 200 | 0 |

#### Clarity
`score = (1 − low_confidence_pct) × 100`
- low_confidence_pct = fraction of words with Whisper confidence < 0.6

#### Filler Words
`score = max(0, 100 − fillers_per_min × 15)`
- 0 fillers/min → 100 · ≥7/min → 0
- Detected words: um, uh, hmm, ah, er, like, basically, you know, I mean, sort of, kind of, right, okay, so, anyway

---

## Layer 2: Sales Quality Score (0–100)

LLM-scored (Ollama `llama3.1:8b`). Implemented in Phase 4.

Each dimension returns: `score (0–10)` + `justification` + `quote from transcript`.

| Dimension | Weight | What is Measured |
|---|---|---|
| Greeting & Introduction | 10% | Professional opener, name/company stated |
| Rapport Building | 10% | Personalisation, active listening |
| Discovery Questions | 15% | Open-ended questions, need exploration |
| Value Explanation | 20% | Benefit articulation tied to prospect's need |
| Objection Handling | 20% | Empathy → acknowledge → address → confirm |
| Script Adherence | 10% | Required talking points from active script |
| Closing & Next Step | 10% | Explicit ask, agreed next action |
| Compliance | 5% | Required disclosures, no prohibited statements |

### Conversion
Each LLM dimension score (0–10) is multiplied by 10 before weighting.

---

## Composite Score
```
speech_composite = Σ (dimension_score × weight)
sales_composite  = Σ (dimension_score × weight)
```
Both are stored on the `calls` table (`speech_score`, `sales_score`) for fast leaderboard ranking and filtering.
