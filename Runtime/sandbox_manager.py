class SandboxManager:
    def __init__(self): self.state={}
    def set_status(self, database_profile_id, sandbox_id, status='ready', schema_snapshot_id=None):
        self.state[(database_profile_id,sandbox_id)]={"status":status,"schema_snapshot_id":schema_snapshot_id,"database_profile_id":database_profile_id,"sandbox_id":sandbox_id}; return self.state[(database_profile_id,sandbox_id)]
    def get_status(self, database_profile_id=None, sandbox_id=None): return self.state.get((database_profile_id,sandbox_id), {"status":"not_configured","database_profile_id":database_profile_id,"sandbox_id":sandbox_id})
