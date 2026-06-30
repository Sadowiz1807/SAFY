from Core.nl.db_intent_parser import parse_db_intent
class RequestPlanner:
    def plan(self, text, snapshot=None): return parse_db_intent(text)
