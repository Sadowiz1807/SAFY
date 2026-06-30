def constraints_from_rules(rules): return [r for r in rules if isinstance(r,dict) and r.get('active',True)]
