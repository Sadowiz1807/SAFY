from __future__ import annotations


def summarize_create_database(chat_id: str, workflow_id: str, workspace_id: str, assumptions: list[str], schema: dict, technical_result: dict, warnings: list[str]) -> dict:
    created_objects = {
        "tables": schema.get("tables", []),
        "views": schema.get("views", []),
        "indexes": schema.get("indexes", []),
        "constraints": schema.get("constraints", []),
    }
    return {
        "chat_id": chat_id,
        "workflow_id": workflow_id,
        "intent": "create_database",
        "assumptions": assumptions,
        "execution_target": "sandbox",
        "workspace_id": workspace_id,
        "status": "success",
        "risk_level": "sandbox_schema_change",
        "summary": "Created a sandbox e-commerce schema.",
        "schema_summary": {"table_count": len(created_objects["tables"]), "tables": created_objects["tables"]},
        "created_objects": created_objects,
        "technical_result": technical_result,
        "warnings": warnings,
        "next_questions": [],
    }
