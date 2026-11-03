# Deutsch von A1 bis B2

A complete, self-study German course covering CEFR levels A1 through B2 — built as a single interactive web app.

**Live app:** https://mustafaalfaisal.github.io/deutsch-a1-b2-course/

(also mirrored as a Claude artifact: https://claude.ai/artifact/VtmsQiutF4FH3BmgJwacfT)

## What's inside

- 60 grammar/topic lessons (15 per level) with explanations, example sentences, tables, and quick-check questions
- 413 vocabulary words and phrases across all four levels, grouped into thematic categories
- Flashcard review mode with flip-to-reveal cards, shuffle, and "still learning" / "know this" tracking
- Multiple-choice practice quizzes generated from each level's vocabulary pool
- Progress tracking and a reset option, stored locally in the browser (no backend)
- Adjustable text size, full light/dark theme support, and a responsive layout down to small phone widths

## Project structure

- `index.html` — the entire app: markup, styles, and logic in one file
- `course_data.json` — all course content (topics + vocabulary), loaded at runtime via `fetch()`
- `vocab_a1.py`, `vocab_a2.py`, `vocab_b1.py`, `vocab_b2.py` — the source vocabulary data, organized by level and category as plain Python tuples
- `build_vocab.py` — merges the four vocab files into `course_data.json` under a `vocabulary` key (also checks for duplicate words within a level)

## Updating vocabulary

Edit the relevant `vocab_*.py` file, then rebuild the data file:

```bash
python3 build_vocab.py
```

This regenerates the `vocabulary` section of `course_data.json` in place.

## Running locally

Any static file server works, since the app loads its data via `fetch()`:

```bash
python3 -m http.server 8000
```

Then open `http://localhost:8000/index.html`.
