import json
from unittest.mock import patch, MagicMock

from runner.supabase_client import submit_run


def test_submit_run_posts_payload():
    fake_response = MagicMock()
    fake_response.read.return_value = json.dumps([{"id": "abc-123"}]).encode()
    fake_response.__enter__ = lambda self: fake_response
    fake_response.__exit__ = lambda self, *a: None

    with patch("urllib.request.urlopen", return_value=fake_response) as mock_open:
        row = submit_run(
            {"handle": "x", "case_id": "y", "agent_label": "z",
             "score": 1, "total": 1, "given": "g", "gold": "g", "verdict": "correct"},
            supabase_url="https://fake.supabase.co",
            anon_key="anon",
        )
    assert row == {"id": "abc-123"}
    mock_open.assert_called_once()
    req = mock_open.call_args[0][0]
    assert req.full_url == "https://fake.supabase.co/rest/v1/runs"
    assert req.headers["Apikey"] == "anon"
