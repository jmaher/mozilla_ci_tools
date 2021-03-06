import json
import os
import unittest

from mock import patch, Mock

from mozci.errors import AuthenticationError
from mozci.sources import buildapi
from mozci.query_jobs import SUCCESS

BASE_JSON = """
[{
    "build_id": 72398103,
    "status": %s,
    "branch": "try",
    "buildername": "Linux x86-64 try build",
    "claimed_by_name": "buildbot-master75.bb.releng.use1.mozilla.com:/builds/buildbot/try1/master",
    "buildnumber": 4372,
    "starttime": 1433164406,
    "requests": [
        {"complete_at": %s,
         "complete": %s,
         "buildername": "Linux x86-64 try build",
         "claimed_at": 1433166028,
         "priority": 0,
         "submittime": 1433164090,
         "reason": "scheduler",
         "branch": "try",
         "request_id": 71123549,
         "revision": "146071751b1e5d16b87786f6e60485222c28c202"}],
    "endtime": %s,
    "revision": "146071751b1e5d16b87786f6e60485222c28c202"}]
"""

JOBS_SCHEDULE = BASE_JSON % (SUCCESS, 1433166610, 1, 1433166609)

REPOSITORIES = """{
    "repo1": {
        "repo": "https://hg.mozilla.org/releases/repo1",
        "graph_branches": ["Repo1"],
        "repo_type": "hg"},
    "repo2": {
        "repo": "https://hg.mozilla.org/projects/repo2",
        "graph_branches": ["Repo2"],
        "repo_type": "hg"}
    }
"""

POST_RESPONSE = """{
    "body": {
        "msg": "Ok",
        "errors": false},
    "request_id": 1234567
    }
"""

BAD_REVISION = """{
    "msg": "Revision 123456123456 not found on branch try",
    "status": "FAILED"
    }
"""


def mock_response(content, status):
    """
    Mock of requests.get().

    The object returned must have content, status_code and reason
    properties and a json method.
    """
    response = Mock()
    response.content = content

    def mock_response_json():
        return json.loads(content)

    response.json = mock_response_json
    response.status_code = status
    response.reason = 'OK'
    return response


class TestQueryRepositories(unittest.TestCase):

    def setUp(self):
        buildapi.REPOSITORIES_FILE = 'tmp_repositories.txt'

    def tearDown(self):
        if os.path.exists('tmp_repositories.txt'):
            os.remove('tmp_repositories.txt')

    @patch('requests.get', return_value=mock_response(REPOSITORIES, 200))
    @patch('mozci.sources.buildapi.get_credentials', return_value=None)
    def test_call_without_any_cache(self, get_credentials, get):
        """Calling the function without disk or in-memory cache."""
        self.assertEquals(
            buildapi.query_repositories(), json.loads(REPOSITORIES))

        self.assertEquals(
            buildapi.REPOSITORIES, json.loads(REPOSITORIES))

    def test_in_memory_cache(self):
        """Calling the function without disk cache but with in-memory cache."""
        buildapi.REPOSITORIES = json.loads(REPOSITORIES)
        self.assertEquals(
            buildapi.query_repositories(), json.loads(REPOSITORIES))

    def test_file_cache(self):
        """Calling the function without in-memory caching but with file cache."""
        buildapi.REPOSITORIES = {}

        # Using a different 'repositories' mock to make sure
        # query_repositories is using the right one.
        different_repositories = {"real-repo": "repo"}
        with open('tmp_repositories.txt', 'w') as f:
            json.dump(different_repositories, f)

        self.assertEquals(
            buildapi.query_repositories(), different_repositories)

    @patch('requests.get', return_value=mock_response(REPOSITORIES, 200))
    @patch('mozci.sources.buildapi.get_credentials', return_value=None)
    def test_with_clobber(self, get_credentials, get):
        """When clobber is True query_repositories should ignore both caches."""
        # Using a different 'repositories' mock to make sure
        # query_repositories is using the right one.
        different_repositories = {"real-repo": "repo"}
        buildapi.REPOSITORIES = different_repositories
        with open('tmp_repositories.txt', 'w') as f:
            json.dump(different_repositories, f)

        self.assertEquals(
            buildapi.query_repositories(clobber=True), json.loads(REPOSITORIES))


class TestQueryRepoUrl(unittest.TestCase):

    @patch('mozci.sources.buildapi.query_repository',
           return_value=json.loads(REPOSITORIES)['repo1'])
    def test_query_repo_url_valid(self, query_repository):
        """Test query_repo_url with a mock value for query_repository."""
        self.assertEquals(
            buildapi.query_repo_url('repo1'), "https://hg.mozilla.org/releases/repo1")

    @patch('mozci.sources.buildapi.query_repository',
           return_value=json.loads(REPOSITORIES))
    def test_query_repo_url_invalid(self, query_repository):
        """query_repo_url should raise an Exception when a repository not in the JSON file."""
        with self.assertRaises(Exception):
            buildapi.query_repo_url("not-a-repo")


class TestQueryRepository(unittest.TestCase):

    """Test query_repository with a mock value for query_repositories."""

    @patch('mozci.sources.buildapi.query_repositories',
           return_value=json.loads(REPOSITORIES))
    def test_query_repository(self, query_repositories):
        """Test with a valid repo name."""
        self.assertEquals(
            buildapi.query_repository('repo1'), json.loads(REPOSITORIES)['repo1'])

    @patch('mozci.sources.buildapi.query_repositories',
           return_value=json.loads(REPOSITORIES))
    def test_invalid(self, query_repositories):
        """query_repository should raise an Exception when the repo is invalid."""
        with self.assertRaises(Exception):
            buildapi.query_repository("not-a-repo")


class TestTriggerJob(unittest.TestCase):

    """Test that trigger_arbitrary_job makes the right POST requests."""

    @patch('requests.post', return_value=mock_response(POST_RESPONSE, 200))
    @patch('mozci.sources.buildapi.get_credentials', return_value=None)
    def test_call_without_dry_run(self, get_credentials, post):
        """trigger_arbitrary_job should call requests.post."""
        buildapi.trigger_arbitrary_job("repo", "builder", "123456123456", dry_run=False)
        # We expect that trigger_arbitrary_job will call requests.post
        # once with the following arguments
        post.assert_called_once_with(
            '%s/%s/builders/%s/%s' % (buildapi.HOST_ROOT, "repo", "builder", "123456123456"),
            headers={'Accept': 'application/json'},
            data={'properties':
                  '{"branch": "repo", "revision": "123456123456"}'},
            auth=get_credentials())

    @patch('requests.post', return_value=mock_response(POST_RESPONSE, 200))
    @patch('mozci.sources.buildapi.get_credentials', return_value=None)
    def test_call_with_dry_run(self, get_credentials, post):
        """trigger_arbitrary_job should return None when dry_run is True."""
        self.assertEquals(
            buildapi.trigger_arbitrary_job("repo", "builder", "123456123456", dry_run=True), None)
        # trigger_arbitrary_job should not call requests.post when dry_run is True
        assert post.call_count == 0

    @patch('requests.post', return_value=mock_response(POST_RESPONSE, 401))
    @patch('mozci.sources.buildapi.get_credentials', return_value=None)
    @patch('mozci.sources.buildapi.remove_credentials', return_value=None)
    def test_bad_response(self, remove_credentials, get_credentials, post):
        """trigger_arbitrary_job should raise an AssertionError if it receives a bad response."""
        with self.assertRaises(AuthenticationError):
            buildapi.trigger_arbitrary_job("repo", "builder", "123456123456", dry_run=False)


class TestMakeRetriggerRequest(unittest.TestCase):

    """Test that make_retrigger_request makes the right POST requests."""

    @patch('requests.post', return_value=mock_response(POST_RESPONSE, 200))
    @patch('mozci.sources.buildapi.get_credentials', return_value=None)
    def test_call_without_dry_run(self, get_credentials, post):
        """trigger_arbitrary_job should call requests.post."""
        buildapi.make_retrigger_request("repo", "1234567", dry_run=False)
        # We expect that make_retrigger_request will call requests.post
        # once with the following arguments
        post.assert_called_once_with(
            '%s/%s/request' % (buildapi.HOST_ROOT, "repo"),
            headers={'Accept': 'application/json'},
            data={'request_id': '1234567'},
            auth=get_credentials())

    @patch('requests.post', return_value=mock_response(POST_RESPONSE, 200))
    @patch('mozci.sources.buildapi.get_credentials', return_value=None)
    def test_call_with_dry_run(self, get_credentials, post):
        """make_retrigger_request should return None when dry_run is True."""
        self.assertEquals(
            buildapi.make_retrigger_request("repo", "1234567", dry_run=True), None)
        # make_retrigger_request should not call requests.post when dry_run is True
        assert post.call_count == 0

    @patch('requests.post', return_value=mock_response(POST_RESPONSE, 200))
    @patch('mozci.sources.buildapi.get_credentials', return_value=None)
    def test_call_with_different_priority(self, get_credentials, post):
        """make_retrigger_request should call requests.post with the right priority."""
        buildapi.make_retrigger_request("repo", "1234567", priority=2, dry_run=False)
        post.assert_called_once_with(
            '%s/%s/request' % (buildapi.HOST_ROOT, "repo"),
            headers={'Accept': 'application/json'},
            data={'count': 1, 'priority': 2, 'request_id': '1234567'},
            auth=get_credentials())

    @patch('requests.post', return_value=mock_response(POST_RESPONSE, 200))
    @patch('mozci.sources.buildapi.get_credentials', return_value=None)
    def test_call_with_different_count(self, get_credentials, post):
        """make_retrigger_request should call requests.post with the right count."""
        buildapi.make_retrigger_request("repo", "1234567", count=10, dry_run=False)
        post.assert_called_once_with(
            '%s/%s/request' % (buildapi.HOST_ROOT, "repo"),
            headers={'Accept': 'application/json'},
            data={'count': 10, 'priority': 0, 'request_id': '1234567'},
            auth=get_credentials())


class TestMakeCancelRequest(unittest.TestCase):

    """Test that make_cancel_request makes the right DELETE requests."""

    @patch('requests.delete', return_value=Mock())
    @patch('mozci.sources.buildapi.get_credentials', return_value=None)
    def test_call_without_dry_run(self, get_credentials, delete):
        """trigger_arbitrary_job should call requests.post."""
        buildapi.make_cancel_request("repo", "1234567", dry_run=False)

        # We expect that make_cancel_request will call requests.delete
        # once with the following arguments
        delete.assert_called_once_with(
            '%s/%s/request/%s' % (buildapi.HOST_ROOT, "repo", "1234567"),
            auth=get_credentials())

    @patch('requests.delete', return_value=Mock())
    @patch('mozci.sources.buildapi.get_credentials', return_value=None)
    def test_call_with_dry_run(self, get_credentials, delete):
        """make_cancel_request should return None when dry_run is True."""
        self.assertEquals(
            buildapi.make_cancel_request("repo", "1234567", dry_run=True), None)
        # make_cancel_request should not call requests.delete when dry_run is True
        assert delete.call_count == 0
