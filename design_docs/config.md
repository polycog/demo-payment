# `payments/config.py` and `config.toml`

## Purpose

One place for every setting, so the demo can be pointed at a different model, policy or customer
without touching code.

## Design

`config.py` does only one thing: `load_config(path)` parses `config.toml` and returns the raw
tables (an empty dict if the file is missing). It knows nothing about what the tables mean.
Each module reads **its own part** and validates it:

| Part of `config.toml` | Read by | Into |
|---|---|---|
| `customer_file` | `bank_payment_service.py` | `CUSTOMER_FILE` (path relative to `config.toml`) |
| `[llm]` | `language.py` | `load_model()` → a pydantic-ai `Model` |
| `[policy]` | `policy.py` | `load_policy_settings()` → `PolicySettings` |

Why this split:

- **No central schema to keep in sync.** Adding a setting means touching only the module that
  uses it.
- **Validation lives with the meaning.** `PolicySettings` is a pydantic model with bounds
  (`gt=0`, …), so a bad value fails at startup with a clear message.
- **Defaults live in code.** A missing table or key falls back to the model's defaults, so the
  file can be partial.

`DEFAULT_CONFIG_PATH` is resolved relative to the package, not the working directory, so
`python -m payments` works from anywhere. Paths inside the file (`customer_file`) are relative
to the file for the same reason.

## `config.toml` at a glance

- **`[llm]`:** `use` picks a profile. A profile with `base_url` is an OpenAI-compatible server
  (`api_key_env` names its key variable, `responses = true` selects the Responses API);
  without `base_url`, `model` is any pydantic-ai model id (e.g. `openai:gpt-4o`).
- **`[policy]`:** `max_amount`, `date_window_days`, `max_verification_attempts`,
  `authenticate_debit_limit_over`. Money is written as strings (`"5000.00"`) so it loads as an
  exact `Decimal`.

## Extending

Add a key under the right table and a matching field (with a default and a description) in
the module that reads it. Don't make `config.py` interpret values.
