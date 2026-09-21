import unittest
from unittest.mock import patch

import erpnext_client


class VerifyLoginTests(unittest.TestCase):
    @patch('erpnext_client.requests.post')
    def test_verify_login_normalizes_email_before_calling_erpnext(self, mock_post):
        class FakeResponse:
            status_code = 200

            @staticmethod
            def json():
                return {"message": "Logged In", "full_name": "Test User"}

        mock_post.return_value = FakeResponse()

        result = erpnext_client.verify_login('  User@Example.com  ', 'MyPassword!')

        self.assertTrue(result['success'])
        self.assertEqual(result['full_name'], 'Test User')
        self.assertEqual(mock_post.call_args.kwargs['data']['usr'], 'user@example.com')


if __name__ == '__main__':
    unittest.main()
