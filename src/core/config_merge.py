def deep_merge(base: dict, override: dict) -> dict:
    """Deep merge override into base. Override values win. Arrays are replaced, not merged."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result
