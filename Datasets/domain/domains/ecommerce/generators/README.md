# Generators

Generators should consume:

```text
domain_manifest.json
business_glossary.json
logical_schema.json
task_templates.json
conversation_templates.json
safety_cases.json
dialects/<database_type>/*
```

Generate samples into `samples/`, then create schema-disjoint splits under `splits/`.

A teacher model may paraphrase user utterances, but it must not be treated as the source of truth for SQL. SQL labels must come from canonical query IR plus dialect generation and execution validation.
