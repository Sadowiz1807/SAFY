class ResponseSynthesizer:
    def ui_patch_for(self, event_type, payload): return {"ui_patch":{"op":"merge","target":event_type,"value":payload}}
