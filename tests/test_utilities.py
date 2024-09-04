import unittest
from lib.utils.utilities import validate_github_url

class TestGitHubURLValidation(unittest.TestCase):

    def test_valid_url(self):
        self.assertTrue(validate_github_url("https://ghp_abc123@github.com/user/repo/"))

    def test_invalid_url_no_key(self):
        self.assertFalse(validate_github_url("https://github.com/user/repo/"))

    def test_invalid_url_wrong_format(self):
        self.assertFalse(validate_github_url("http://ghp_abc123@github.com/user/repo/"))

    def test_invalid_url_missing_project(self):
        self.assertFalse(validate_github_url("https://ghp_abc123@github.com/user/"))

if __name__ == '__main__':
    unittest.main()
