# Migration

Old:

```text
DomainBuild/
DomainIntelligence/
DomainPacks/
```

New:

```text
DomainIntelligence/
├── runtime modules
├── packs/
├── reports/
└── work/  # compiler tạo khi cần
```

`DomainIntelligence/registry.py` vẫn hỗ trợ đọc `DomainPacks/registry.json` cũ như fallback trong giai đoạn chuyển đổi.
