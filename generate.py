"""
Multilingual prompt bank generator for misinformation/fact-checking research.

For each language in COUNTRY_LANGS, this script:
  1. Loads country name translations from a CSV.
  2. Loads named entities (politicians, cities, etc.) per country from an Excel file.
  3. Fills placeholders in prompt templates (e.g. [COUNTRY], [CITY]) with real entities.
  4. Writes one JSON file per language: prompt_bank_in_{lang}.json

Each entry in the output JSON is a tuple:
  (filled_prompt, topic, original_template, prompt_id)

Input files (all expected in the working directory):
  - countries-translations.csv       — country name translations across all 8 languages
  - parallel_templates.xlsx          — prompt templates with placeholders, sheet "TemplatesFinalized"
  - parallel_entities.xlsx           — named entities per country, sheet "Final"
"""

import pandas as pd
import json
import re
import csv
import random
import itertools
from collections import defaultdict

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# Seed for reproducible sampling when N_SAMPLES < total combinations.
random.seed(42)

# Set of placeholder names (without brackets) recognised as valid entity slots.
# Any placeholder in a template that is NOT in this set is ignored.
ENTITY_LIST = {"COUNTRY", "NATIONALITY", "CITY", "POLITICAL_FIGURE", "PUBLIC_FIGURE", "RELIGION", "NEWS"}

# Maps placeholder names (as they appear in templates) to entity type strings
# used in parallel_entities.xlsx — "Entity Type" column.
PLACEHOLDER_TO_ENTITY_TYPE = {
    "CITY": "City",
    "NATIONALITY": "Nationality",
    "NEWS": "News Agency",
    "POLITICAL_FIGURE": "Political Figure",
    "PUBLIC_FIGURE": "Public Figure",
    "RELIGION": "Religious Group",
}

# Languages to generate output for. Must match column headers in both
# parallel_templates.xlsx and parallel_entities.xlsx.
COUNTRY_LANGS = ["Igbo", "Turkish", "Farsi", "Arabic", "English", "Urdu", "French", "Nepali"]

# Number of filled prompts to sample per (template, country) pair.
# Increase to get more coverage of entity combinations; set to None to keep all.
N_SAMPLES = 1

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def substitute_placeholders(template: str, values_map: dict) -> str:
    """Replace every [PLACEHOLDER] in *template* using *values_map*.

    Unknown placeholders are left as-is.

    Args:
        template:   Raw template string, e.g. "Tell me about [COUNTRY]."
        values_map: Dict mapping bracketed placeholder to its replacement,
                    e.g. {"[COUNTRY]": "Nigeria"}.

    Returns:
        Template with all known placeholders substituted.
    """
    return re.sub(r"(\[[A-Z_]+\])", lambda m: values_map.get(m.group(0), m.group(0)), template)


def load_country_translations(filepath: str) -> dict:
    """Load country name translations from a CSV file.

    The CSV must have columns (no strict header required beyond position):
      country, Igbo, Turkish, Farsi, French, Nepali, Urdu, Arabic

    The English name is taken as the country identifier (column 0).

    Args:
        filepath: Path to the CSV file.

    Returns:
        Dict mapping English country name → {lang: translated_name, ...}
        e.g. {"Nigeria": {"English": "Nigeria", "Igbo": "Naijiria", ...}, ...}
    """
    translations = {}
    with open(filepath, encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        next(reader)  # skip header row
        for row in reader:
            translations[row[0]] = dict(zip(
                ["English", "Igbo", "Turkish", "Farsi", "French", "Nepali", "Urdu", "Arabic"],
                [row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7]]
            ))
    return translations


def load_entity_dataset(filepath: str, lang: str) -> dict:
    """Load named entities from parallel_entities.xlsx for a given language.

    Reads the "Final" sheet. Expected columns:
      Country, Entity Type, English, Igbo, Turkish, Farsi, French, Nepali, Urdu, Arabic

    Args:
        filepath: Path to the entities Excel file.
        lang:     Language name matching a column header (e.g. "English", "Igbo").

    Returns:
        Nested dict: {country: {entity_type: [entity, ...], ...}, ...}
        e.g. {"Nigeria": {"City": ["Lagos", "Abuja"], "Political Figure": [...], ...}, ...}
    """
    df = pd.read_excel(filepath, sheet_name="Final")
    dataset = defaultdict(lambda: defaultdict(list))
    for country, category, entity in zip(df["Country"], df["Entity Type"], df[lang]):
        dataset[country][category].append(entity)
    return dataset


def extract_valid_placeholders(template: str) -> list:
    """Return all [PLACEHOLDER] tokens in *template* that are in ENTITY_LIST.

    Args:
        template: Raw template string.

    Returns:
        List of bracketed placeholder strings, e.g. ["[COUNTRY]", "[CITY]"].
    """
    return [e for e in re.findall(r"\[[^\[\]]+\]", template) if e.strip("[]") in ENTITY_LIST]


def build_prompts_for_country(country, template, placeholders, entity_dataset, country_translations, lang):
    """Generate filled prompts for a single (country, template) pair.

    For each placeholder, looks up the available entities for *country* and
    *lang*, then takes the Cartesian product of all combinations before
    sampling N_SAMPLES of them.

    Returns None if any placeholder has no available entities for this country
    (the (template, country) pair is silently skipped by the caller).

    Args:
        country:              English country name, e.g. "Nigeria".
        template:             Template string with placeholders.
        placeholders:         List of bracketed placeholder strings found in template.
        entity_dataset:       Output of load_entity_dataset.
        country_translations: Output of load_country_translations.
        lang:                 Target language name.

    Returns:
        List of filled prompt strings (length ≤ N_SAMPLES), or None if data
        is missing for this (country, template) pair.
    """
    entity_values = {}
    for ph in placeholders:
        entity_name = ph.strip("[]")
        if entity_name == "COUNTRY":
            entity_values[ph] = [country_translations[country][lang]]
        else:
            entity_type = PLACEHOLDER_TO_ENTITY_TYPE.get(entity_name, entity_name)
            values = entity_dataset[country].get(entity_type, [])
            if values:
                entity_values[ph] = values

    # Bail out if any placeholder has no entities for this country
    if len(entity_values) != len(placeholders) or any(len(v) == 0 for v in entity_values.values()):
        return None

    unique_phs = sorted(set(placeholders))
    combinations = list(itertools.product(*(entity_values[ph] for ph in unique_phs)))
    sentences = [substitute_placeholders(template, dict(zip(unique_phs, combo))) for combo in combinations]
    return random.sample(sentences, min(N_SAMPLES, len(sentences)))


def generate_prompt_bank(lang: str, templates_df, entity_dataset, country_translations) -> dict:
    """Build the full prompt bank for one language.

    Iterates over every template × country combination, calling
    build_prompts_for_country to fill placeholders. Missing data for a
    (template, country) pair is counted as an error and skipped.

    Args:
        lang:                 Target language name.
        templates_df:         DataFrame from parallel_templates.xlsx.
        entity_dataset:       Output of load_entity_dataset for *lang*.
        country_translations: Output of load_country_translations.

    Returns:
        Dict mapping country → list of (prompt, topic, template, prompt_id) tuples.
    """
    prompt_bank = {country: [] for country in entity_dataset}
    total, errors = 0, 0

    for _, row in templates_df.iterrows():
        template = row[lang]
        if not isinstance(template, str):
            continue

        placeholders = extract_valid_placeholders(template)
        if not placeholders:
            print(f"No valid placeholders: {lang} {row['Prompt ID']}")
            continue

        for country in prompt_bank:
            results = build_prompts_for_country(
                country, template, placeholders, entity_dataset, country_translations, lang
            )
            if results:
                entries = [(s, row["Topic"], template, row["Prompt ID"]) for s in results]
                prompt_bank[country].extend(entries)
                total += len(entries)
            else:
                errors += 1

    print(f"{lang}: {total} prompts, {errors} errors")
    return prompt_bank


def main():
    country_translations = load_country_translations("countries-translations.csv")
    templates_df = pd.read_excel("parallel_templates.xlsx", sheet_name="TemplatesFinalized")

    for lang in COUNTRY_LANGS:
        entity_dataset = load_entity_dataset("parallel_entities.xlsx", lang)
        prompt_bank = generate_prompt_bank(lang, templates_df, entity_dataset, country_translations)

        with open(f"prompt_bank_in_{lang}.json", "w", encoding="utf-8") as f:
            json.dump(prompt_bank, f, indent=4, ensure_ascii=False)


if __name__ == "__main__":
    main()
