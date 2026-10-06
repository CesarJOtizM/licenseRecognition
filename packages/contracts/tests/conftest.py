from typing import Any

import pytest


@pytest.fixture
def payload() -> dict[str, Any]:
    return {
        "plate": "ABC123",
        "raw_text": "ABC-123",
        "confidence": 0.93,
        "captured_at": "2026-10-04T13:00:00Z",
        "lane_id": "entrada-1",
        "source": "pipeline",
    }
