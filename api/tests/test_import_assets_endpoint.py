import os
import shutil
import tempfile

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from api.tests import APIBaseTestCase
from core.models import Asset

User = get_user_model()
client = APIClient()


class AssetsUploadTestCase(APIBaseTestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            email='admin@site.com', cohort=20,
            slack_handle='@admin', password='devpassword'
        )
        self.token_admin = 'admintesttoken'

        self.asset_uploads_url = reverse('import-assets')
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_non_authenticated_user_view_assets(self):
        response = client.get(self.asset_uploads_url)
        self.assertEqual(response.data, {
            'detail': 'Authentication credentials were not provided.'
        })

    @patch('api.authentication.auth.verify_id_token')
    def test_authenticated_user_can_upload_csv_file_to_save_assets(self, mock_verify_id_token):
        mock_verify_id_token.return_value = {'email': self.admin_user.email}
        data = {}

        file_location = os.path.join(os.path.dirname(__file__), 'sample.csv')
        initial_count = Asset.objects.count()

        with open(file_location) as csv:
            data['file'] = csv
            response = client.post(
                self.asset_uploads_url,
                data=data,
                HTTP_AUTHORIZATION="Token {}".format(self.token_admin))
        final_count = Asset.objects.count()
        self.assertEqual(1, final_count - initial_count)
        self.assertEqual(200, response.status_code)

    @patch('api.authentication.auth.verify_id_token')
    def test_no_file_provided(self, mock_verify_id_token):
        mock_verify_id_token.return_value = {'email': self.admin_user.email}
        initial_count = Asset.objects.count()
        response = client.post(
            self.asset_uploads_url,
            data={},
            HTTP_AUTHORIZATION="Token {}".format(self.token_admin))
        final_count = Asset.objects.count()
        self.assertEqual(0, final_count - initial_count)
        self.assertEqual(400, response.status_code)

    @patch('api.authentication.auth.verify_id_token')
    def test_file_process_error(self, mock_verify_id_token):
        mock_verify_id_token.return_value = {'email': self.admin_user.email}
        initial_count = Asset.objects.count()
        data = {}
        file = tempfile.TemporaryFile()
        data['file'] = file
        response = client.post(
            self.asset_uploads_url,
            data=data,
            HTTP_AUTHORIZATION="Token {}".format(self.token_admin))
        final_count = Asset.objects.count()
        self.assertEqual(0, final_count - initial_count)
        self.assertEqual(500, response.status_code)

    @patch('api.authentication.auth.verify_id_token')
    def test_uploading_assets_already_in_the_database_skips_saving_them(self, mock_verify_id_token):
        mock_verify_id_token.return_value = {'email': self.admin_user.email}
        data = {}

        file_location = os.path.join(os.path.dirname(__file__), 'sample_with_duplicates.csv')
        initial_count = Asset.objects.count()
        with open(file_location) as csv:
            data['file'] = csv
            response = client.post(
                self.asset_uploads_url,
                data=data,
                HTTP_AUTHORIZATION="Token {}".format(self.token_admin))
        final_count = Asset.objects.count()
        self.assertIn('skipped_assets', response.data.get('message'))
        self.assertEqual(1, final_count - initial_count)
