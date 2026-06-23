import requests
import pytest
import os
from pathlib import Path
BASE = "https://api.h4s.live"

# Token may live in the real environment (os.environ) OR in a .env file at the
# repo root. .env names it API_TOKEN; the environment names it H4S_TOKEN. Accept
# either name from either source so the suite runs in both setups.
TOKEN_NAMES = ("H4S_TOKEN", "API_TOKEN")


def _load_dotenv():
    """Parse the nearest .env walking up from this file. Returns a dict.

    Deliberately dependency-free (no python-dotenv): handles KEY=VALUE lines,
    skips blanks/comments, strips surrounding quotes and an optional `export`.
    """
    values = {}
    for parent in Path(__file__).resolve().parents:
        env_path = parent / ".env"
        if env_path.is_file():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                if line.startswith("export "):
                    line = line[len("export "):]
                key, _, val = line.partition("=")
                values[key.strip()] = val.strip().strip("'").strip('"')
            break
    return values


def _resolve_token():
    """Return the API token from os.environ first, then .env. None if absent."""
    for name in TOKEN_NAMES:
        if os.environ.get(name):
            return os.environ[name]
    dotenv = _load_dotenv()
    for name in TOKEN_NAMES:
        if dotenv.get(name):
            return dotenv[name]
    return None

def test_heatlh_returns_200():
    assert requests.get(f"{BASE}/health").status_code == 200
    
def test_requires_auth_returns_401():
    assert requests.get(f"{BASE}/api/applications").status_code == 401
    
TestAuthHead = {
    "Authorization": "Bearer definitely_not_valid"
}

def test_bad_token_returns_401():
    assert requests.get(f"{BASE}/api/applications", headers=TestAuthHead).status_code == 401
    
@pytest.fixture(scope="module")
def auth_headers():
    token = _resolve_token()
    if not token:
        pytest.skip("no API token in os.environ or .env (H4S_TOKEN / API_TOKEN)")
    return {"Authorization": f"Bearer {token}"}

def test_list_applications_returns_200(auth_headers):
    r = requests.get(f"{BASE}/api/applications/", headers=auth_headers)
    assert r.status_code == 200

def test_dashboard_stats_returns_200(auth_headers):
    assert requests.get(f"{BASE}/api/dashboard/stats", headers=auth_headers).status_code == 200
    
@pytest.fixture(scope="module")
def auth_session(auth_headers):
    s = requests.Session()
    s.headers.update(auth_headers)
    yield s
    s.close()
    
def test_session_lists_applications(auth_session):
    assert auth_session.get(f"{BASE}/api/applications/").status_code == 200
    
def test_session_resuses_auth_across_calls(auth_session):
    assert auth_session.get(f"{BASE}/api/applications/").status_code == 200
    assert auth_session.get(f"{BASE}/api/dashboard/stats").status_code == 200
    
@pytest.mark.parametrize("endpoints", ["/api/applications/", "/api/dashboard/stats", "/api/applications/openclaw-status"])
def test_protected_routes_require_401(endpoints):
    assert requests.get(f"{BASE}{endpoints}").status_code == 401
    
@pytest.mark.parametrize("endpoints", ["/api/applications/", "/api/dashboard/stats", "/api/applications/openclaw-status"])
def test_protected_routes_with_auth_200(auth_session, endpoints):
    assert auth_session.get(f"{BASE}{endpoints}").status_code == 200
    
def test_missing_application_returns_404(auth_session):
    assert auth_session.get(f"{BASE}/api/applications/whateverthisis").status_code == 404
    
def test_search_too_short_returns_422(auth_session):
    assert auth_session.get(f"{BASE}/api/applications/search?q=a").status_code == 422
    
def test_search_valid_query(auth_session):
    assert auth_session.get(f"{BASE}/api/applications/search?q=hello").status_code == 200
    
def test_list_returns_a_json_list(auth_session):
    data = auth_session.get(f"{BASE}/api/applications/")
    assert isinstance(data.json(), list)
    
def test_application_item_schema(auth_session):
    data = auth_session.get(f"{BASE}/api/applications/").json()
    if data:
        item = data[0]
        assert {"job_id", "company", "role", "status", "fit_score"} <= set(item)
        assert isinstance(item["job_id"], str)
        assert isinstance(item["status"], str)
        assert isinstance(item["starred"], bool)

def test_dashboard_stats_schema(auth_session):
    data = auth_session.get(f"{BASE}/api/dashboard/stats").json()
    if data:
        assert {"total", "status_counts", "response_rate", "interview_rate", "offer_rate", "response_count"} <= set(data)
        
def test_health_body_is_ok():
    assert requests.get(f"{BASE}/health").json() == {"status": "ok"}


# =====================================================================
# PYTEST MECHANICS REFERENCE (for the interview)
# =====================================================================
#
# 1. @pytest.mark.skipif(condition, reason="...")  -- CONDITIONAL SKIP
#    What: before running, pytest checks the condition. If True, the test
#          is SKIPPED (yellow 's'), not run. (@pytest.mark.skip = always.)
#    Why:  a missing precondition should bow out cleanly (skip), not look
#          like a real failure (error/red). Skip = "not applicable here".
#    Use:  authed tests need H4S_TOKEN. A teammate with no token should see
#          "skipped", not a KeyError. -> skipif(not os.environ.get("H4S_TOKEN"))
#          Also common: skipif(sys.platform == "win32") for OS-only tests.
#
# 2. @pytest.mark.slow  (custom marker) + `pytest -m`  -- TAGGING / SUBSETS
#    What: a marker is just a LABEL on a test. Changes nothing about how it
#          runs; lets you FILTER: `pytest -m slow` (only) / `-m "not slow"`
#          (exclude). Register the name in pytest.ini to silence warnings.
#    Why:  big suites mix fast + expensive tests. Run fast ones constantly,
#          slow/network ones on demand.
#    Use:  tag live-network tests @pytest.mark.network. Daily: `-m "not
#          network"` (instant, offline). CI/pre-push: full run. Ties to
#          CI/CD: fast tests gate every commit, slow suite runs nightly.
#
# 3. @pytest.fixture(params=[...])  -- PARAMETRIZED FIXTURE
#    What: the FIXTURE holds the value list; exposes each via request.param.
#          EVERY test using the fixture runs once per value. Define inputs
#          once; all consumers inherit them.
#    Why:  when many tests should run over the SAME variant set, repeating
#          @parametrize on each is duplication. Centralize it on the fixture.
#    Use:  a `db` fixture with params=["sqlite","postgres","mysql"] -> every
#          test taking `db` runs 3x, proving the suite passes on all backends.
#    Distinction: @parametrize varies the input to ONE test; a parametrized
#                 fixture varies a shared resource across ALL tests using it.
#
# 4. conftest.py  -- SHARED FIXTURES, NO IMPORTS
#    What: a magic filename pytest auto-loads. Fixtures defined there are
#          available to every test file in that folder/subfolders with NO
#          import statement.
#    Why:  once two files need the same fixture, don't copy-paste -- define
#          it once in conftest.py and both just use it.
#    Use:  split into test_auth.py + test_reads.py; move auth_headers /
#          auth_session into api_tests/conftest.py -> both files find them.
#
# Through-line: these four are about SCALING a suite -- skip (env-graceful),
# markers (run subsets), parametrized fixtures (shared input matrices),
# conftest (shared setup). Basic asserts prove you CAN test; these prove you
# can ORGANIZE a real framework ("build scalable automation frameworks").
# =====================================================================