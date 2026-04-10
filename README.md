# GlobalLies

Official repository for the ACL 2026 Paper: [**To Lie or Not to Lie? Investigating The Biased Spread of Global Lies by LLMs**](https://arxiv.org/abs/2604.06552)

## Overview

GlobalLies investigates whether large language models propagate misinformation in a biased way across countries and languages. The dataset consists of multilingual prompts derived from real-world misinformation claims, covering 8 languages and multiple countries.

## Repository structure

| File/Folder | Description |
|---|---|
| `generate.py` | Generates the multilingual prompt bank from templates and entities |
| `parallel_templates.xlsx` | Prompt templates with entity placeholders (e.g. `[COUNTRY]`, `[CITY]`) |
| `parallel_entities.xlsx` | Named entities (politicians, cities, etc.) per country and language |
| `countries-translations.csv` | Country name translations across all 8 languages |
| `factual_prompts.xlsx` | Concrete factual-claim prompts (no placeholders) |
| `misinformation_prompts.xlsx` | Concrete misinformation-claim prompts (no placeholders) |

## Generating the prompt bank

Requirements: Python 3.11+, `pandas`, `openpyxl`.

```bash
python generate.py
```

This writes one JSON file per language into the working directory.

Each file maps country names to a list of `(prompt, topic, template, prompt_id)` tuples.

Key parameters in `generate.py` (see the Config section at the top of the file):

- `N_SAMPLES` — number of filled prompts sampled per template × country pair (default: 1)
- `COUNTRY_LANGS` — list of languages to generate; subset for faster runs
- `random.seed(42)` — controls sampling reproducibility

## Citation

If you use this dataset or code, please cite:

```bibtex
@misc{khan2026lielieinvestigatingbiased,
      title={To Lie or Not to Lie? Investigating The Biased Spread of Global Lies by LLMs}, 
      author={Zohaib Khan and Mustafa Dogan and Ifeoma Okoh and Pouya Sadeghi and Siddhartha Shrestha and Sergius Justus Nyah and Mahmoud O. Mokhiamar and Michael J. Ryan and Tarek Naous},
      year={2026},
      eprint={2604.06552},
      archivePrefix={arXiv},
      primaryClass={cs.CL},
      url={https://arxiv.org/abs/2604.06552}, 
}
```
