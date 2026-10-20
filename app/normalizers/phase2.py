def normalize_phase2(*payloads: dict) -> dict:
    """Combine canonical Phase 2 evidence; absent provider data remains absent."""
    signals: dict = {}
    for payload in payloads:
        signals.update({key: value for key, value in payload.items() if value is not None})
    return signals
