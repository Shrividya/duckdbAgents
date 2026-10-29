# duckdbAgents

A Claude-powered data analyst agent that answers natural-language questions by querying a read-only DuckDB database of the [Olist Brazilian e-commerce dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce).

## Setup

```bash
uv sync
```

Create a `.env` file:

```
ANTHROPIC_API_KEY=...
MOTHERDUCK_TOKEN=...
```

Download the Olist CSVs into `data/`, then build the database:

```bash
uv run build_db.py
```

## Usage

Ask a question:

```bash
uv run agent.py olist.duckdb "Which product categories have the highest revenue?"
```

Run the evals (optionally pass a case number to run one):

```bash
uv run eval.py olist.duckdb [case_number]
```

## Files

| File | Purpose |
| --- | --- |
| `agent.py` | Agent loop, system prompt, JSON-lines logging to `logs/` |
| `tools.py` | `list_tables`, `describe_table`, `run_sql` (row cap and timeout) |
| `build_db.py` | Loads the CSVs into `olist.duckdb` |
| `eval.py` | Compares agent answers against reference SQL |
