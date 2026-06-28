# SAFY Domain Intelligence

`DomainIntelligence` is the runtime package for compiled business-domain knowledge and semantic schema design.

```text
DomainIntelligence/
├── compiler.py                 # optional source-dataset compiler
├── registry.py                 # portable compiled-pack registry
├── router.py                   # lexical evidence/fallback router
├── context_builder.py          # bounded cited retrieval context
├── schema_workflow.py          # active semantic classification + schema DDL workflow
├── packs/
│   ├── registry.json           # canonical runtime catalog
│   ├── cache/
│   └── <domain>/<version>/<domain>.safy-domain
├── reports/
└── work/                       # compiler workspace only
```

## Runtime contract

- Compiled packs are the only domain catalog.
- The active model classifies meaning semantically using the full catalog; the lexical router is evidence/fallback, not the sole classifier.
- Domain IDs are validated against the registry.
- Ambiguous requests require clarification; there is no default e-commerce domain.
- `/Execute` schema design loads the selected pack and permits only bounded CREATE TABLE/INDEX DDL.
- Server-level CREATE DATABASE and unsafe statements are rejected before Execute Box.
- User Check Safety validates the exact batch in sandbox before real Execute.

## Dataset boundary
The source `Datasets/domain/` tree is needed only to rebuild packs. A lightweight runtime handoff may omit it while keeping all compiled packs and runtime behavior.
