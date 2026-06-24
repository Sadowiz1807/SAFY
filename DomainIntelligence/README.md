# SAFY Domain Intelligence

Ba thư mục cấp cao cũ đã được gộp thành một package duy nhất:

```text
DomainIntelligence/
├── *.py
├── packs/
│   ├── registry.json
│   ├── cache/
│   └── <domain_id>/<version>/<domain_id>.safy-domain
├── reports/
└── work/        # chỉ được tạo khi compiler chạy
```

## Thay đổi

- Bỏ `DomainBuild/` ở cấp project.
- Bỏ `DomainPacks/` ở cấp project.
- Bỏ `__pycache__` và các file `.pyc`.
- Không đóng gói `staging/` và `source_repairs/` rỗng.
- Registry sử dụng đường dẫn tương đối, không hard-code máy người build.
- Runtime vẫn import bằng package `DomainIntelligence`, nên không phá API import cũ.

## Cài vào project

Xóa hoặc đổi tên ba thư mục cũ, sau đó chép thư mục `DomainIntelligence` mới vào project root.
