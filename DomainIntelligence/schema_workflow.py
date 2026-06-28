from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable
import json
import re

from Gateway.sql_classifier import CREATE, classify_sql
from Gateway.sql_normalizer import normalize_sql, sanitize_sql_input
from Gateway.statement_target_extractor import extract_targets
from LLM.provider_health import adapter_for

from .context_builder import DomainContextBuilder
from .pack_reader import DomainPackReader
from .registry import DomainRegistry
from .router import DomainRouter


SCHEMA_INTENT = "create_domain_schema"
CATALOG_INTENT = "list_domain_catalog"
OTHER_INTENT = "other"
UNKNOWN_INTENT = "unknown"

SUPPORTED_SCHEMA_DIALECTS = {
    "postgres": "postgresql",
    "postgresql": "postgresql",
    "supabase": "supabase_rpc",
    "supabase_rpc": "supabase_rpc",
    "mysql": "mysql",
    "sqlite": "sqlite",
    "sqlserver": "sqlserver",
    "mssql": "sqlserver",
    "oracle": "oracle",
}


@dataclass(frozen=True)
class DomainCatalogEntry:
    domain_id: str
    domain_name: str
    pack_version: str
    entities: list[str] = field(default_factory=list)
    positive_signals: list[str] = field(default_factory=list)
    supported_database_types: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DomainSchemaResolution:
    relevant: bool
    intent: str
    decision: str
    domain_id: str | None = None
    confidence: float = 0.0
    candidates: list[str] = field(default_factory=list)
    rationale: str = ""
    warnings: list[str] = field(default_factory=list)
    source: str = "runtime"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DomainSchemaDesign:
    domain_id: str
    domain_name: str
    dialect: str
    sql: str
    statements: list[str]
    table_names: list[str]
    assumptions: list[str]
    warnings: list[str]
    explanation: str
    citations: list[dict[str, Any]]
    model_profile_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DomainSchemaWorkflowError(Exception):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        self.code = code
        self.details = details or {}
        super().__init__(message)


class DomainSchemaWorkflow:
    """Canonical domain-schema design workflow for the active AgentRuntime.

    DomainIntelligence compiled packs are the only runtime catalog. The model is
    used as a semantic classifier and schema designer, but every returned domain
    identifier and every DDL statement is validated against deterministic local
    contracts before it can reach the Execute Box.
    """

    def __init__(
        self,
        root: str | Path,
        provider_store: Any,
        adapter_factory: Callable[[dict[str, Any]], Any] = adapter_for,
    ) -> None:
        self.root = Path(root).resolve()
        self.provider_store = provider_store
        self.adapter_factory = adapter_factory
        self.registry = DomainRegistry(self.root)
        self.context_builder = DomainContextBuilder(self.root)

    def catalog(self) -> list[DomainCatalogEntry]:
        entries: list[DomainCatalogEntry] = []
        for row in self.registry.enabled_packs():
            try:
                reader = DomainPackReader(row["path"])
                try:
                    manifest = reader.manifest
                    ontology = reader.read_json("ontology.json")
                    labels = reader.read_json("router/labels.json")
                finally:
                    reader.close()
            except Exception:
                continue
            entries.append(
                DomainCatalogEntry(
                    domain_id=str(row.get("domain_id") or manifest.get("domain_id") or ""),
                    domain_name=str(manifest.get("domain_name") or row.get("domain_id") or ""),
                    pack_version=str(row.get("pack_version") or manifest.get("pack_version") or ""),
                    entities=[str(value) for value in (ontology.get("entities") or []) if str(value).strip()],
                    positive_signals=[str(value) for value in (labels.get("positive_signals") or []) if str(value).strip()],
                    supported_database_types=[str(value) for value in (manifest.get("supported_database_types") or []) if str(value).strip()],
                )
            )
        return sorted(entries, key=lambda item: item.domain_id)

    def catalog_dicts(self) -> list[dict[str, Any]]:
        return [entry.to_dict() for entry in self.catalog()]

    def catalog_answer(self) -> str:
        entries = self.catalog()
        if not entries:
            return "DomainIntelligence chưa có compiled domain pack khả dụng."
        lines = ["SAFY hiện có các domain schema pack trong DomainIntelligence:"]
        for entry in entries:
            examples = ", ".join(self._business_entities(entry)[:6])
            suffix = f" — ví dụ thực thể: {examples}" if examples else ""
            lines.append(f"- {entry.domain_name} (`{entry.domain_id}`){suffix}")
        lines.append("Khi yêu cầu đủ rõ, SAFY có thể tự phân loại. Nếu có nhiều domain hợp lý hoặc độ tin cậy thấp, SAFY sẽ hỏi lại thay vì tự mặc định.")
        return "\n".join(lines)

    @staticmethod
    def normalize_dialect(value: str | None) -> str | None:
        key = str(value or "").strip().lower()
        return SUPPORTED_SCHEMA_DIALECTS.get(key)

    def resolve_request(
        self,
        message: str,
        *,
        model_profile_id: str | None = None,
        pending_candidates: list[str] | None = None,
        original_request: str | None = None,
    ) -> DomainSchemaResolution:
        text = str(message or "").strip()
        if not text:
            return DomainSchemaResolution(False, UNKNOWN_INTENT, "none", rationale="empty_request")

        catalog = self.catalog()
        catalog_by_id = {entry.domain_id: entry for entry in catalog}
        if not catalog:
            return DomainSchemaResolution(
                True,
                SCHEMA_INTENT,
                "blocked",
                rationale="No compiled DomainIntelligence packs are available.",
                warnings=["domain_registry_empty"],
            )

        exact_matches = self._exact_domain_matches(text, catalog)
        exact = exact_matches[0] if len(exact_matches) == 1 else None
        lexical = DomainRouter(self.registry.enabled_packs()).route(text, "")
        model_payload = self._semantic_classify(
            text,
            catalog,
            model_profile_id=model_profile_id,
            pending_candidates=pending_candidates,
            original_request=original_request,
            lexical=lexical.to_dict(),
        )

        if model_payload is not None:
            intent = str(model_payload.get("intent") or UNKNOWN_INTENT).strip().lower()
            if intent not in {SCHEMA_INTENT, CATALOG_INTENT, OTHER_INTENT, UNKNOWN_INTENT}:
                intent = UNKNOWN_INTENT
            relevant = intent in {SCHEMA_INTENT, CATALOG_INTENT}
            if intent == CATALOG_INTENT:
                return DomainSchemaResolution(True, intent, "catalog", confidence=self._float01(model_payload.get("confidence")), rationale=str(model_payload.get("rationale") or ""), source="semantic_model")
            if intent != SCHEMA_INTENT:
                return DomainSchemaResolution(False, intent, "none", confidence=self._float01(model_payload.get("confidence")), rationale=str(model_payload.get("rationale") or ""), source="semantic_model")

            raw_candidates = model_payload.get("candidates") or []
            if isinstance(raw_candidates, str):
                raw_candidates = [raw_candidates]
            candidates = [str(value).strip() for value in raw_candidates if str(value).strip() in catalog_by_id]
            selected = str(model_payload.get("domain_id") or "").strip()
            if selected not in catalog_by_id:
                selected = ""
            confidence = self._float01(model_payload.get("confidence"))
            ambiguous = bool(model_payload.get("ambiguous"))

            # Exact catalog names/ids are deterministic evidence and may resolve
            # harmless spelling/casing differences without overriding ambiguity
            # between different domain meanings.
            if exact and not ambiguous and len(candidates) <= 1 and (not selected or confidence < 0.60):
                selected = exact
                confidence = max(confidence, 0.98)
            if selected and selected not in candidates:
                candidates.insert(0, selected)

            if selected and confidence >= 0.75 and not ambiguous:
                return DomainSchemaResolution(True, intent, "selected", selected, confidence, candidates[:5], str(model_payload.get("rationale") or ""), source="semantic_model")
            return DomainSchemaResolution(
                True,
                intent,
                "clarify",
                selected or None,
                confidence,
                candidates[:5] or self._lexical_candidates(lexical, catalog_by_id),
                str(model_payload.get("rationale") or "The requested business domain is not unambiguous."),
                warnings=["domain_clarification_required"],
                source="semantic_model",
            )

        # Offline/model-unavailable fallback. This path never defaults to a
        # domain. It selects only exact catalog identity or a strong, separated
        # DomainRouter result. Everything else asks for clarification.
        fallback_intent = self._fallback_schema_intent(text, original_request=original_request)
        if not fallback_intent:
            return DomainSchemaResolution(False, OTHER_INTENT, "none", source="fallback")
        if self._fallback_catalog_intent(text):
            return DomainSchemaResolution(True, CATALOG_INTENT, "catalog", confidence=0.8, source="fallback")
        if len(exact_matches) > 1:
            return DomainSchemaResolution(
                True,
                SCHEMA_INTENT,
                "clarify",
                None,
                1.0,
                exact_matches[:5],
                "Multiple exact DomainIntelligence catalog identities are present in the request.",
                warnings=["multiple_exact_domain_matches"],
                source="fallback",
            )
        if exact:
            return DomainSchemaResolution(True, SCHEMA_INTENT, "selected", exact, 1.0, [exact], "Exact DomainIntelligence catalog match.", source="fallback")
        if lexical.selected_domain_id and lexical.decision == "selected" and lexical.confidence >= 0.35:
            return DomainSchemaResolution(True, SCHEMA_INTENT, "selected", lexical.selected_domain_id, lexical.confidence, self._lexical_candidates(lexical, catalog_by_id), "Strong compiled-pack router evidence.", source="fallback")
        return DomainSchemaResolution(
            True,
            SCHEMA_INTENT,
            "clarify",
            lexical.selected_domain_id,
            lexical.confidence,
            self._lexical_candidates(lexical, catalog_by_id),
            "A model is unavailable or the compiled-pack evidence is not decisive.",
            warnings=["semantic_model_unavailable_or_ambiguous"],
            source="fallback",
        )

    def design_schema(
        self,
        *,
        request: str,
        domain_id: str,
        dialect: str,
        model_profile_id: str | None = None,
        max_tables: int = 18,
        max_statements: int = 64,
    ) -> DomainSchemaDesign:
        entry = next((item for item in self.catalog() if item.domain_id == domain_id), None)
        if entry is None:
            raise DomainSchemaWorkflowError("DOMAIN_PACK_NOT_FOUND", f"Domain pack not found: {domain_id}")
        normalized_dialect = self.normalize_dialect(dialect)
        if normalized_dialect is None:
            raise DomainSchemaWorkflowError("SCHEMA_DIALECT_UNSUPPORTED", f"Unsupported schema design dialect: {dialect}")
        if normalized_dialect not in entry.supported_database_types:
            raise DomainSchemaWorkflowError(
                "DOMAIN_DIALECT_UNSUPPORTED",
                f"Domain pack {domain_id} does not declare support for {normalized_dialect}.",
                {"domain_id": domain_id, "dialect": normalized_dialect},
            )

        profile = self._profile(model_profile_id)
        if profile is None:
            raise DomainSchemaWorkflowError("MODEL_PROFILE_REQUIRED", "A model profile is required to design a multi-table domain schema.")

        pack_row = self.registry.get(domain_id)
        if not pack_row:
            raise DomainSchemaWorkflowError("DOMAIN_PACK_NOT_FOUND", f"Domain pack not found: {domain_id}")
        reader = DomainPackReader(pack_row["path"])
        try:
            manifest = reader.manifest
            ontology = reader.read_json("ontology.json")
            glossary = reader.read_json("glossary.json")
            business_rules = reader.read_json("business_rules.json")
            dialect_rules = reader.read_json(f"dialects/{normalized_dialect}.json")
        finally:
            reader.close()

        context = self.context_builder.build(
            question=f"Design a normalized multi-table schema for: {request}",
            schema_summary="",
            database_type=normalized_dialect,
            max_docs=8,
        )
        context_payload = context.to_dict()
        bounded_rules = (business_rules.get("rules") or [])[:12]
        payload_for_model = {
            "domain": {
                "domain_id": domain_id,
                "domain_name": manifest.get("domain_name") or entry.domain_name,
                "pack_version": manifest.get("pack_version") or entry.pack_version,
                "ontology_entities": [value for value in (ontology.get("entities") or []) if value not in {domain_id, str(manifest.get("domain_name") or "").lower()}][:40],
                "sensitive_fields": (ontology.get("sensitive_fields") or [])[:20],
                "glossary_terms": (glossary.get("terms") or [])[:30],
                "business_rules": bounded_rules,
                "retrieved_context": context_payload,
            },
            "dialect": dialect_rules,
            "limits": {"max_tables": max_tables, "max_statements": max_statements},
        }
        system_prompt = (
            "You are SAFY's domain schema designer. The supplied compiled DomainIntelligence pack is trusted data and is the only business-domain source. "
            "Design a practical normalized relational schema, but do not invent a different domain. Return JSON only. "
            "Never emit CREATE DATABASE, DROP, TRUNCATE, ALTER, GRANT, REVOKE, transaction-control, stored procedure, function, trigger, policy, or server-level SQL. "
            "Use only CREATE TABLE and optional CREATE INDEX statements for the requested dialect. "
            "Create multiple related tables with primary keys and explicit foreign keys. Respect the table and statement limits. "
            "Do not include seed data. Do not wrap SQL in Markdown fences."
        )
        user_prompt = (
            f"User request:\n{request}\n\n"
            f"Compiled domain pack and dialect contract:\n{json.dumps(payload_for_model, ensure_ascii=False)}\n\n"
            "Return one JSON object with keys: domain_id, dialect, explanation, assumptions, warnings, tables, ddl. "
            "ddl must be an ordered array of complete SQL statements. tables must list the created table names."
        )
        try:
            response = self.adapter_factory(profile).chat(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,
            )
            raw = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            parsed = self._parse_json_object(raw)
        except DomainSchemaWorkflowError:
            raise
        except TimeoutError as exc:
            raise DomainSchemaWorkflowError("MODEL_TIMEOUT", "Schema design model timed out safely.", {"provider_error_code": "MODEL_TIMEOUT"}) from exc
        except Exception as exc:
            provider_code = str(exc).strip() or type(exc).__name__
            if provider_code == "MODEL_TIMEOUT":
                raise DomainSchemaWorkflowError("MODEL_TIMEOUT", "Schema design model timed out safely.", {"provider_error_code": "MODEL_TIMEOUT"}) from exc
            safe_code = provider_code if re.match(r"^(BLOCKED_LLM|MODEL_TIMEOUT|LLM|PROVIDER)[A-Z0-9_]*$", provider_code) else type(exc).__name__
            raise DomainSchemaWorkflowError("DOMAIN_SCHEMA_MODEL_FAILED", "Schema design model failed safely.", {"provider_error_code": safe_code}) from exc

        model_domain = str(parsed.get("domain_id") or "").strip()
        if model_domain != domain_id:
            raise DomainSchemaWorkflowError(
                "DOMAIN_SCHEMA_DOMAIN_MISMATCH",
                "The schema designer returned a different domain than the selected DomainIntelligence pack.",
                {"expected": domain_id, "actual": model_domain},
            )
        model_dialect = self.normalize_dialect(str(parsed.get("dialect") or normalized_dialect))
        if model_dialect != normalized_dialect:
            raise DomainSchemaWorkflowError(
                "DOMAIN_SCHEMA_DIALECT_MISMATCH",
                "The schema designer returned SQL for a different dialect.",
                {"expected": normalized_dialect, "actual": model_dialect},
            )

        ddl = parsed.get("ddl") or []
        if isinstance(ddl, str):
            ddl = normalize_sql(sanitize_sql_input(ddl)).statements
        if not isinstance(ddl, list):
            raise DomainSchemaWorkflowError("DOMAIN_SCHEMA_DDL_INVALID", "Schema designer ddl must be an array or SQL string.")
        raw_sql = ";\n\n".join(str(item).strip().rstrip(";") for item in ddl if str(item).strip())
        normalized = normalize_sql(raw_sql)
        statements = normalized.statements
        if not statements:
            raise DomainSchemaWorkflowError("DOMAIN_SCHEMA_DDL_EMPTY", "Schema designer returned no DDL.")
        if len(statements) > max_statements:
            raise DomainSchemaWorkflowError("DOMAIN_SCHEMA_BATCH_TOO_LARGE", f"Schema design exceeds {max_statements} statements.")

        table_names: list[str] = []
        create_table_count = 0
        for index, statement in enumerate(statements, start=1):
            classification = classify_sql(statement)
            if classification.statement_type != CREATE:
                raise DomainSchemaWorkflowError(
                    "DOMAIN_SCHEMA_STATEMENT_BLOCKED",
                    "Only CREATE TABLE/INDEX statements are allowed in a generated domain schema batch.",
                    {"statement_index": index, "statement_type": classification.statement_type},
                )
            upper = statement.upper()
            if not re.match(r"^\s*CREATE\s+(?:UNIQUE\s+)?(?:TABLE|INDEX)\b", upper):
                raise DomainSchemaWorkflowError(
                    "DOMAIN_SCHEMA_CREATE_TYPE_BLOCKED",
                    "Only CREATE TABLE and CREATE INDEX are allowed in a generated schema batch.",
                    {"statement_index": index},
                )
            if re.match(r"^\s*CREATE\s+TABLE\b", upper):
                create_table_count += 1
            extraction = extract_targets(classification)
            if not extraction.targets:
                raise DomainSchemaWorkflowError(
                    "DOMAIN_SCHEMA_TARGET_UNRESOLVED",
                    "A generated CREATE statement has no safely extractable target.",
                    {"statement_index": index},
                )
            for target in extraction.targets:
                clean = str(target).strip()
                if clean and clean not in table_names:
                    table_names.append(clean)

        if create_table_count < 2:
            raise DomainSchemaWorkflowError("DOMAIN_SCHEMA_REQUIRES_MULTIPLE_TABLES", "A domain database design must create at least two related tables.")
        if create_table_count > max_tables:
            raise DomainSchemaWorkflowError("DOMAIN_SCHEMA_TOO_MANY_TABLES", f"Schema design exceeds {max_tables} tables.")

        sql = ";\n\n".join(statement.rstrip(";") for statement in statements) + ";"
        assumptions = [str(value) for value in (parsed.get("assumptions") or []) if str(value).strip()]
        warnings = [str(value) for value in (parsed.get("warnings") or []) if str(value).strip()]
        explanation = str(parsed.get("explanation") or f"Generated a {entry.domain_name} schema draft for {normalized_dialect}.").strip()
        return DomainSchemaDesign(
            domain_id=domain_id,
            domain_name=entry.domain_name,
            dialect=normalized_dialect,
            sql=sql,
            statements=statements,
            table_names=table_names,
            assumptions=assumptions,
            warnings=warnings,
            explanation=explanation,
            citations=context.citations,
            model_profile_id=str(profile.get("profile_id") or model_profile_id or "") or None,
        )

    def clarification_question(self, candidates: list[str] | None = None) -> str:
        catalog_by_id = {entry.domain_id: entry for entry in self.catalog()}
        valid = [value for value in (candidates or []) if value in catalog_by_id]
        if valid:
            labels = ", ".join(f"{catalog_by_id[value].domain_name} (`{value}`)" for value in valid[:5])
            return f"Yêu cầu có thể thuộc nhiều domain. Bạn muốn thiết kế theo domain nào: {labels}?"
        return self.catalog_answer() + "\nBạn hãy chọn một domain hoặc mô tả rõ nghiệp vụ cần quản lý."

    def preview(self, domain_id: str, dialect: str | None = None) -> dict[str, Any]:
        entry = next((item for item in self.catalog() if item.domain_id == domain_id), None)
        if entry is None:
            raise DomainSchemaWorkflowError("DOMAIN_PACK_NOT_FOUND", f"Domain pack not found: {domain_id}")
        return {
            "domain_id": entry.domain_id,
            "domain_name": entry.domain_name,
            "pack_version": entry.pack_version,
            "dialect": self.normalize_dialect(dialect),
            "entities": self._business_entities(entry)[:24],
            "supported_database_types": list(entry.supported_database_types),
        }

    def _profile(self, model_profile_id: str | None) -> dict[str, Any] | None:
        try:
            return self.provider_store.get(model_profile_id, redacted=False) if model_profile_id else self.provider_store.active(redacted=False)
        except Exception:
            return None

    def _semantic_classify(
        self,
        message: str,
        catalog: list[DomainCatalogEntry],
        *,
        model_profile_id: str | None,
        pending_candidates: list[str] | None,
        original_request: str | None,
        lexical: dict[str, Any],
    ) -> dict[str, Any] | None:
        profile = self._profile(model_profile_id)
        if profile is None:
            return None
        compact_catalog = [
            {
                "domain_id": entry.domain_id,
                "domain_name": entry.domain_name,
                "representative_entities": self._business_entities(entry)[:10],
            }
            for entry in catalog
        ]
        system = (
            "Classify the user's meaning semantically, not by requiring fixed keywords. Return JSON only. "
            "Intent create_domain_schema means designing a new multi-table relational schema/domain database, not querying or editing an existing table and not creating one isolated table. "
            "Intent list_domain_catalog means asking which business-domain schema templates SAFY can design. "
            "Select only domain_id values from the provided compiled DomainIntelligence catalog. "
            "If multiple domains are plausible, the request is broad, or confidence is below 0.75, set ambiguous=true and provide candidates. "
            "Never default to ecommerce. Typos may suggest candidates but require clarification unless the intended catalog domain remains unambiguous."
        )
        user = {
            "message": message,
            "original_request": original_request,
            "pending_candidates": pending_candidates or [],
            "compiled_domain_catalog": compact_catalog,
            "lexical_router_evidence": lexical,
            "output_contract": {
                "intent": f"one of [{SCHEMA_INTENT}, {CATALOG_INTENT}, {OTHER_INTENT}, {UNKNOWN_INTENT}]",
                "domain_id": "catalog id or null",
                "confidence": "0..1",
                "ambiguous": "boolean",
                "candidates": "ordered catalog ids",
                "rationale": "short explanation",
            },
        }
        try:
            payload = self.adapter_factory(profile).chat(
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
                ],
                temperature=0.0,
            )
            raw = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
            return self._parse_json_object(raw)
        except Exception:
            return None

    @staticmethod
    def _parse_json_object(content: Any) -> dict[str, Any]:
        if isinstance(content, dict):
            return content
        if isinstance(content, list):
            text = "\n".join(str(item.get("text") or item.get("content") or item) if isinstance(item, dict) else str(item) for item in content)
        else:
            text = str(content or "")
        text = text.strip()
        fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.I | re.S)
        if fenced:
            text = fenced.group(1).strip()
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                parsed = json.loads(match.group(0))
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass
        raise DomainSchemaWorkflowError("MODEL_JSON_INVALID", "Model did not return the required JSON object.")

    @staticmethod
    def _float01(value: Any) -> float:
        try:
            return max(0.0, min(float(value), 1.0))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _business_entities(entry: DomainCatalogEntry) -> list[str]:
        ignored = {entry.domain_id, entry.domain_name.strip().lower(), entry.domain_name.strip().lower().replace("&", "and")}
        return [entity for entity in entry.entities if entity.strip().lower() not in ignored]

    @staticmethod
    def _exact_domain_matches(message: str, catalog: list[DomainCatalogEntry]) -> list[str]:
        normalized = re.sub(r"[^a-z0-9]+", " ", message.lower()).strip()
        matches: list[str] = []
        for entry in catalog:
            forms = {
                re.sub(r"[^a-z0-9]+", " ", entry.domain_id.lower()).strip(),
                re.sub(r"[^a-z0-9]+", " ", entry.domain_name.lower()).strip(),
            }
            if any(form and re.search(rf"\b{re.escape(form)}\b", normalized) for form in forms):
                matches.append(entry.domain_id)
        return matches

    @staticmethod
    def _lexical_candidates(route: Any, catalog_by_id: dict[str, DomainCatalogEntry]) -> list[str]:
        candidates = []
        for candidate in getattr(route, "candidates", []) or []:
            value = getattr(candidate, "domain_id", None)
            if value in catalog_by_id and value not in candidates:
                candidates.append(value)
        return candidates[:5]

    @staticmethod
    def _fallback_catalog_intent(message: str) -> bool:
        text = message.lower()
        return bool(re.search(r"(?:những|các|which|what).{0,30}(?:domain|mẫu|template|loại).{0,30}(?:database|cơ sở dữ liệu|schema)|(?:database|schema).{0,30}(?:nào|what|which)", text, re.I))

    @staticmethod
    def _fallback_schema_intent(message: str, *, original_request: str | None = None) -> bool:
        text = f"{original_request or ''} {message}".lower()
        # Fallback only. The primary route is semantic-model classification.
        # This recognizes broad design language and does not select a domain.
        creation = re.search(r"\b(create|design|build|generate|tạo|tao|thiết kế|thiet ke|xây dựng|xay dung|khởi tạo|khoi tao)\b", text, re.I)
        schema_noun = re.search(r"\b(database|db|schema|cơ sở dữ liệu|co so du lieu|csdl|hệ thống dữ liệu|he thong du lieu)\b", text, re.I)
        multi_table = re.search(r"\b(multi[- ]?table|nhiều bảng|nhieu bang|toàn bộ nghiệp vụ|toan bo nghiep vu|quản lý|quan ly)\b", text, re.I)
        return bool(creation and (schema_noun or multi_table))
