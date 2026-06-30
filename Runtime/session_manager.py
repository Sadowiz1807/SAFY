class SessionManager:
    def __init__(self): self.sessions={}
    def create_session(self, session_id, database_profile_id=None, sandbox_id=None, model=None):
        self.sessions[session_id]={"session_id":session_id,"database_profile_id":database_profile_id,"sandbox_id":sandbox_id,"model":model,"context_files":[],"ui":{}}
        return self.sessions[session_id]
    def update_session(self, session_id, **fields):
        if session_id not in self.sessions: self.create_session(session_id)
        allowed={"database_profile_id","sandbox_id","model","context_files","ui","rules_version"}
        bad=set(fields)-allowed
        if bad: return {"error":{"code":"INVALID_SESSION_UPDATE","fields":sorted(bad)}}
        self.sessions[session_id].update(fields); return self.sessions[session_id]
    def get_session(self, session_id): return self.sessions.get(session_id) or self.create_session(session_id)
