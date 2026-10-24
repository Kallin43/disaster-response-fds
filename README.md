# Data-Driven Disaster Response

An interactive, coded analytics dashboard for the supplied 70-record India EM-DAT extract. It explores event frequency and reported impacts to support discussion of relief planning.

> **Tableau assignment note:** This is a Streamlit implementation of equivalent dashboard requirements; it is not Tableau. Since your assignment explicitly names Tableau, obtain faculty approval before submitting Streamlit as a substitute.

## Project files

- `app.py` — Streamlit application, calculations, charts, validation, and custom CSS.
- `real_india_disasters_70_EMDAT.csv` — supplied CSV placed beside the application.
- `requirements.txt` — Python dependencies.

## Run locally on macOS

Use Python 3.9 or newer. From Terminal, change to the folder containing `app.py`, then run:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
streamlit run app.py
```

If the dataset is missing, put `real_india_disasters_70_EMDAT.csv` in the same folder as `app.py`. The dashboard shows a notice and does not use fabricated or sample data.

## What the dashboard contains

- A slim `FIELD / ANALYTICS` header with an interactive Data notes popover.
- A responsive editorial hero with the dataset year range and source-integrity message.
- Global filters for disaster type, year range, and the numeric severity source level, plus **Clear all**.
- Four filtered KPI cards: event count, reported deaths, reported affected population, and average reported economic loss.
- An annual event-count time series.
- A disaster-type impact profile with a selector for deaths, affected population, homeless population, or economic loss when those fields are present.
- A searchable source-record table, with original CSV headers and values retained, followed by methodology notes.

All filters affect the KPI cards, charts, and table. Search narrows the already filtered table. Clear all restores the initial full-data selection.

## Missing values and metric definitions

- Missing impact values remain missing; they are not treated as confirmed zero impacts.
- Reported deaths and affected population are sums of non-missing values. Affected population uses the supplied `total_affected` field.
- Average reported economic loss is calculated over non-missing `economic_loss_000_usd` values. The source unit is thousand USD, shown as USD thousands (`k`). If no values are reported, the KPI displays an em dash.
- Impact charts exclude missing values and show how many records report the selected metric in hover details.
- The severity field is presented as the numeric value supplied in the CSV. The extract does not document how it was derived, so this app does not claim that it is an official EM-DAT classification.
- Invalid dates are excluded from the year filter and time-series chart; their original values remain in the source-record table.
- The dashboard analyzes the supplied extract but does not independently verify the underlying records.
