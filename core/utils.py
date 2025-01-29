import json
from datetime import datetime

class JEncoder(json.JSONEncoder):
    # Override default() method
    def default(self, obj):
        # Datetime to isoformat string
        if isinstance(obj, datetime):
            return obj.isoformat()

        # Default behavior for all other types
        return super().default(obj)