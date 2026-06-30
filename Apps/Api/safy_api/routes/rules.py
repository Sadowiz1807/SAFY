from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, model_validator
from Apps.Api.safy_api.runtime_store import envelope, error_envelope
from Runtime.strict_services import list_rules as list_rules_service, save_rule as save_rule_service, disable_rule as disable_rule_service, RULE_STORE, RULE_ENGINE, _schema_for_rule_profile
from Runtime.live_runtime import RULE_MANAGER, EVENT_BUS

router = APIRouter()

class RuleDraftPayload(BaseModel):
    raw_text: str = ''
    rule_id: str | None = None
    database_profile_id: str | None = None
    sandbox_id: str = 'sandbox_default'
    connection_name: str | None = None
    source_type: str = 'manual_text'
    source_filename: str | None = None
    severity: str = 'block'
    model_config = ConfigDict(extra='allow')

    @model_validator(mode='before')
    @classmethod
    def accept_legacy_rule_text_alias(cls, data):
        if isinstance(data, dict) and not data.get('raw_text') and data.get('rule_text') is not None:
            data = dict(data)
            data['raw_text'] = data.get('rule_text')
        return data

class RuleActionPayload(BaseModel):
    rule_id: str
    database_profile_id: str | None = None
    sandbox_id: str = 'sandbox_default'
    model_config = ConfigDict(extra='allow')

@router.get('/sandbox-rules')
def sandbox_rules_route(database_profile_id: str = 'db_default', sandbox_id: str = 'sandbox_default'):
    try:
        return envelope(list_rules_service(database_profile_id, sandbox_id))
    except Exception as exc:
        return error_envelope('SANDBOX_RULE_LIST_FAILED', 'Sandbox rules could not be listed safely.', {'error_type': type(exc).__name__})

@router.post('/sandbox-rules/draft')
def sandbox_rule_draft_route(payload: RuleDraftPayload):
    rule = RULE_STORE.create_draft(database_profile_id=payload.database_profile_id or 'db_default', sandbox_id=payload.sandbox_id, raw_text=payload.raw_text, connection_name=payload.connection_name, source_type=payload.source_type, source_filename=payload.source_filename, severity=payload.severity)
    return envelope({'rule': rule, 'served_by': 'routes/rules.py'})

@router.post('/sandbox-rules/save')
def sandbox_rule_save_route(payload: RuleDraftPayload):
    try:
        result = save_rule_service(payload.model_dump())
        rule = result.get('rule') if isinstance(result, dict) else None
        if not result.get('saved'):
            report = result.get('validation_report') or {}
            warnings = report.get('warnings') or []
            raw_text = (payload.raw_text or '').strip()
            code = 'RULE_TEXT_REQUIRED' if not raw_text else 'RULE_AMBIGUOUS'
            message = 'Rule text is required.' if not raw_text else 'Rule is ambiguous and was not activated.'
            return error_envelope(code, message, {'saved': False, 'status': report.get('status'), 'warnings': warnings, 'compiler_status': warnings[0] if warnings else report.get('status')})
        if rule:
            EVENT_BUS.emit('rules.saved', {'rule_id': rule.get('rule_id'), 'served_by': 'routes/rules.py'})
        return envelope(result)
    except Exception as exc:
        return error_envelope('SANDBOX_RULE_SAVE_FAILED', 'Sandbox rule save failed safely.', {'error_type': type(exc).__name__})

@router.post('/sandbox-rules/validate')
def sandbox_rule_validate_route(payload: RuleActionPayload):
    rule = RULE_STORE.get_rule(payload.database_profile_id or 'db_default', payload.sandbox_id, payload.rule_id)
    if not rule:
        return error_envelope('SANDBOX_RULE_NOT_FOUND', 'Sandbox rule was not found.')
    report = RULE_ENGINE.validate_rule(rule, RULE_STORE.list_rules(payload.database_profile_id or 'db_default', payload.sandbox_id).get('active_rules', []), _schema_for_rule_profile(payload.database_profile_id))
    rule['parsed_rules'] = report.get('parsed_rules', [])
    rule['status'] = report.get('status', rule.get('status', 'draft'))
    RULE_STORE.save_rule(rule)
    path = RULE_STORE.write_validation_report(rule, report)
    return envelope({'rule': rule, 'validation_report': report, 'validation_report_path': str(path), 'served_by': 'routes/rules.py'})

@router.post('/sandbox-rules/activate')
def sandbox_rule_activate_route(payload: RuleActionPayload):
    rule = RULE_STORE.get_rule(payload.database_profile_id or 'db_default', payload.sandbox_id, payload.rule_id)
    if not rule:
        return error_envelope('SANDBOX_RULE_NOT_FOUND', 'Sandbox rule was not found.')
    active = RULE_STORE.list_rules(payload.database_profile_id or 'db_default', payload.sandbox_id).get('active_rules', [])
    updated, report = RULE_ENGINE.activate(rule, active, _schema_for_rule_profile(payload.database_profile_id))
    RULE_STORE.save_rule(updated)
    RULE_STORE.write_validation_report(updated, report)
    return envelope({'rule': updated, 'validation_report': report, 'served_by': 'routes/rules.py'})

@router.post('/sandbox-rules/disable')
def sandbox_rule_disable_route(payload: RuleActionPayload):
    rule = disable_rule_service(payload.model_dump())
    if not rule:
        return error_envelope('SANDBOX_RULE_NOT_FOUND', 'Active sandbox rule was not found.')
    EVENT_BUS.emit('rules.disabled', {'rule_id': payload.rule_id, 'served_by': 'routes/rules.py'})
    return envelope({'rule': rule, 'served_by': 'routes/rules.py'})

@router.post('/sandbox-rules/upload')
async def sandbox_rule_upload_route(request: Request):
    payload = await request.json()
    filename = str(payload.get('filename') or 'rule.txt')
    if not (filename.lower().endswith('.md') or filename.lower().endswith('.txt')):
        return error_envelope('SANDBOX_RULE_UNSUPPORTED_FILE_TYPE', 'Sandbox rule files must be .md or .txt.')
    content = str(payload.get('content') or payload.get('raw_text') or '')
    result = save_rule_service({'database_profile_id': payload.get('database_profile_id'), 'sandbox_id': payload.get('sandbox_id') or 'sandbox_default', 'raw_text': content, 'source_type': 'file_upload', 'source_filename': filename})
    return envelope(result)

@router.get('/sandbox-rules/{rule_id}/validation-report')
def sandbox_rule_validation_report_route(rule_id: str, database_profile_id: str, sandbox_id: str = 'sandbox_default'):
    reports = sorted((RULE_STORE.scope_dir(database_profile_id, sandbox_id) / 'validation_reports').glob(f'{rule_id}_*.json'))
    if not reports:
        return error_envelope('SANDBOX_RULE_VALIDATION_REPORT_NOT_FOUND', 'No validation report found for this rule.')
    import json
    return envelope(json.loads(reports[-1].read_text(encoding='utf-8')))
