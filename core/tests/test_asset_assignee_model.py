from django.db import IntegrityError

from core.models import AssetAssignee, Department, OfficeFloorSection, \
    OfficeFloor, OfficeBlock, OfficeWorkspace
from core.tests import CoreBaseTestCase

from django.contrib.auth import get_user_model

User = get_user_model()


class AssetAssigneeModelTest(CoreBaseTestCase):
    """Tests for AssetAssignee Model"""

    def setUp(self):
        super(AssetAssigneeModelTest, self).setUp()
        self.user = User.objects.create(
            email='test@site.com', cohort=10,
            slack_handle='@test_user', password='devpassword'
        )
        self.department = Department.objects.create(name="Finance")
        self.office_block = OfficeBlock.objects.create(name='Andela Tower')
        self.office_floor = OfficeFloor.objects.create(
            block=self.office_block,
            number=14
        )
        self.office_section = OfficeFloorSection.objects.create(
            name='Safari',
            floor=self.office_floor
        )

    def test_asset_assignee_is_created_when_a_user_is_saved(self):
        """
        Test every time a user is created, an asset assignee
         associated with this user is created
        """
        user = User.objects.create(
            email='test1@site.com', cohort=10,
            slack_handle='@test_user', password='devpassword'
        )
        self.assertEqual(len(AssetAssignee.objects.filter(user=user)), 1)

    def test_asset_assignee_is_created_when_a_department_is_saved(self):
        """
        Test every time a new department is saved,
        an associated asset assignee is created.
        """
        department = Department.objects.create(name="Success")
        self.assertEqual(len(AssetAssignee.objects.filter(
            department=department)), 1)

    def test_asset_assignee_is_created_when_a_workspace_is_saved(self):
        """
        Test every time a new department is saved,
        an associated asset assignee is created.
        """
        workspace = OfficeWorkspace.objects.create(
            name="Success",
            section=self.office_section
        )
        self.assertEqual(len(AssetAssignee.objects.filter(
            workspace=workspace)), 1)

    def test_every_asset_assignee_is_unique(self):
        """
        Test every asset_assignee can only be associated
        with only one user.
        """
        with self.assertRaises(IntegrityError):
            User.objects.create(
                email='test@site.com', cohort=10,
                slack_handle='@test_user', password='devpassword'
            )
