# Scoring Rubric — Sales Call Analyzer

> This document is populated during Phase 3 (Speech Quality) and Phase 4 (Sales Quality).

## Speech Quality Score (Layer 1) — Dimensions

| Dimension    | Tool               | Weight | Notes |
|---|---|---|---|
| Pronunciation | Whisper confidence | 15%    | TBD   |
| Intonation   | parselmouth F0 std | 15%    | TBD   |
| Fluency      | librosa pause data | 15%    | TBD   |
| Grammar      | LanguageTool       | 15%    | TBD   |
| Vocabulary   | spaCy TTR          | 10%    | TBD   |
| Pace         | WPM from timestamps| 10%    | TBD   |
| Clarity      | Whisper confidence | 10%    | TBD   |
| Filler Words | Regex              | 10%    | TBD   |

## Sales Quality Score (Layer 2) — Dimensions

| Dimension              | Weight | Prompt Notes |
|---|---|---|
| Greeting & Introduction | 10%   | TBD          |
| Rapport Building        | 10%   | TBD          |
| Discovery Questions     | 15%   | TBD          |
| Value Explanation       | 20%   | TBD          |
| Objection Handling      | 20%   | TBD          |
| Script Adherence        | 10%   | TBD          |
| Closing & Next Step     | 10%   | TBD          |
| Compliance              | 5%    | TBD          |
