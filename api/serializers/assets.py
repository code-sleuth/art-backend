# Third-Party Imports
from django.core.exceptions import ValidationError
from rest_framework import serializers

# App Imports
from core import models
from core.constants import CHECKIN, CHECKOUT


class AssetSerializer(serializers.ModelSerializer):
    checkin_status = serializers.SerializerMethodField()
    allocation_history = serializers.SerializerMethodField()
    assigned_to = serializers.SerializerMethodField()
    asset_category = serializers.SerializerMethodField()
    asset_sub_category = serializers.SerializerMethodField()
    make_label = serializers.SerializerMethodField()
    asset_type = serializers.SerializerMethodField()
    asset_location = serializers.SlugRelatedField(
        many=False,
        slug_field='centre_name',
        required=False,
        queryset=models.AndelaCentre.objects.all(),
    )

    model_number = serializers.SlugRelatedField(
        queryset=models.AssetModelNumber.objects.all(), slug_field="model_number"
    )

    class Meta:
        model = models.Asset
        fields = (
            'id',
            'uuid',
            'asset_category',
            'asset_sub_category',
            'make_label',
            'asset_code',
            'serial_number',
            'model_number',
            'checkin_status',
            'created_at',
            'last_modified',
            'current_status',
            'asset_type',
            'allocation_history',
            'specs',
            'purchase_date',
            'notes',
            'assigned_to',
            'asset_location',
            'verified',
        )
        depth = 1
        read_only_fields = (
            "uuid",
            "created_at",
            "last_modified",
            "assigned_to",
            "current_status",
            "notes",
        )

    def _asset_make(self, obj):
        return obj.model_number.make_label

    def get_checkin_status(self, obj):
        try:
            asset_log = (
                models.AssetLog.objects.filter(asset=obj)
                .order_by('-created_at')
                .first()
            )
            if asset_log.log_type == CHECKIN:
                return "checked_in"
            elif asset_log.log_type == CHECKOUT:
                return "checked_out"
        except AttributeError:
            return None

    def get_assigned_to(self, obj):
        if not obj.assigned_to:
            return None
        if obj.assigned_to.department:
            from api.serializers import DepartmentSerializer

            serialized_data = DepartmentSerializer(obj.assigned_to.department)
        elif obj.assigned_to.workspace:
            from api.serializers import OfficeWorkspaceSerializer

            serialized_data = OfficeWorkspaceSerializer(obj.assigned_to.workspace)
        elif obj.assigned_to.user:
            from api.serializers import UserSerializer

            serialized_data = UserSerializer(obj.assigned_to.user)
        else:
            return None
        return serialized_data.data

    def get_asset_category(self, obj):
        asset_make = self._asset_make(obj)
        return asset_make.asset_type.asset_sub_category.asset_category.category_name

    def get_asset_sub_category(self, obj):
        asset_make = self._asset_make(obj)
        return asset_make.asset_type.asset_sub_category.sub_category_name

    def get_make_label(self, obj):
        asset_make = self._asset_make(obj)
        return asset_make.make_label

    def get_asset_type(self, obj):
        asset_make = self._asset_make(obj)
        return asset_make.asset_type.asset_type

    def get_allocation_history(self, obj):
        allocations = models.AllocationHistory.objects.filter(asset=obj.id)
        return [
            {
                "id": allocation.id,
                "current_owner": allocation.current_owner.email
                if allocation.current_owner
                else None,
                "previous_owner": allocation.previous_owner.email
                if allocation.previous_owner
                else None,
                "created_at": allocation.created_at,
            }
            for allocation in allocations
        ]

    def to_internal_value(self, data):
        internals = super(AssetSerializer, self).to_internal_value(data)
        specs_serializer = AssetSpecsSerializer(data=data)
        specs_serializer.is_valid()

        if len(specs_serializer.data):
            try:
                specs, _ = models.AssetSpecs.objects.get_or_create(
                    **specs_serializer.data
                )
            except ValidationError as err:
                raise serializers.ValidationError(err.error_dict)
            internals['specs'] = specs
        return internals


class AssetAssigneeSerializer(serializers.ModelSerializer):
    assignee = serializers.SerializerMethodField()

    class Meta:
        model = models.AssetAssignee
        fields = ("id", "assignee")

    def get_assignee(self, obj):
        if obj.user:
            return obj.user.email

        elif obj.department:
            return obj.department.name

        elif obj.workspace:
            return obj.workspace.name


class AssetLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.AssetLog
        fields = ("id", "asset", "log_type", "created_at", "last_modified")

    def to_representation(self, instance):
        instance_data = super().to_representation(instance)
        asset = models.Asset.objects.get(id=instance.asset.id)
        serial_no = asset.serial_number
        asset_code = asset.asset_code
        instance_data['checked_by'] = instance.checked_by.email
        instance_data['asset'] = f"{serial_no} - {asset_code}"
        return instance_data


class AssetStatusSerializer(AssetSerializer):
    status_history = serializers.SerializerMethodField()

    class Meta:
        model = models.AssetStatus
        fields = (
            "id",
            "asset",
            "current_status",
            "status_history",
            "previous_status",
            "created_at",
        )

    def get_status_history(self, obj):
        asset_status = models.AssetStatus.objects.filter(asset=obj.asset)
        return [
            {
                "id": asset.id,
                "asset": asset.asset_id,
                "current_status": asset.current_status,
                "previous_status": asset.previous_status,
                "created_at": asset.created_at,
            }
            for asset in asset_status
            if obj.created_at > asset.created_at
        ]

    def to_representation(self, instance):
        instance_data = super().to_representation(instance)
        serial_no = instance.asset.serial_number
        asset_code = instance.asset.asset_code
        instance_data['asset'] = f"{asset_code} - {serial_no}"
        return instance_data


class AllocationsSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.AllocationHistory
        fields = ("asset", "current_owner", "previous_owner", "created_at")
        read_only_fields = ("previous_owner",)

    def to_representation(self, instance):
        instance_data = super().to_representation(instance)
        serial_no = instance.asset.serial_number
        asset_code = instance.asset.asset_code

        if instance.previous_owner:
            instance_data['previous_owner'] = instance.previous_owner.email
        if instance.current_owner:
            instance_data['current_owner'] = instance.current_owner.email
        instance_data['asset'] = f"{serial_no} - {asset_code}"
        return instance_data


class AssetCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.AssetCategory
        fields = ("id", "category_name", "created_at", "last_modified")


class AssetSubCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.AssetSubCategory
        fields = (
            "id",
            "sub_category_name",
            "asset_category",
            "created_at",
            "last_modified",
        )

    def to_representation(self, instance):
        instance_data = super().to_representation(instance)
        instance_data['asset_category'] = instance.asset_category.category_name
        return instance_data


class AssetTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.AssetType
        fields = (
            "id",
            "asset_type",
            "asset_sub_category",
            "has_specs",
            "created_at",
            "last_modified",
        )

    def to_representation(self, instance):
        instance_data = super().to_representation(instance)
        instance_data[
            'asset_sub_category'
        ] = instance.asset_sub_category.sub_category_name
        return instance_data


class AssetModelNumberSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.AssetModelNumber
        fields = ('id', 'model_number', 'make_label', 'created_at', 'last_modified')

    def to_representation(self, instance):
        instance_data = super().to_representation(instance)
        instance_data['make_label'] = models.AssetMake.objects.get(
            id=instance.make_label.id
        ).make_label
        return instance_data

    def to_internal_value(self, data):
        make_label = data.get('make_label')
        if not make_label:
            raise serializers.ValidationError(
                {'make_label': [self.error_messages['required']]}
            )
        try:
            make_label_instance = models.AssetMake.objects.get(id=make_label)
        except Exception:
            raise serializers.ValidationError(
                {
                    'make_label': [
                        f'Invalid pk \"{make_label}\" - object does not exist.'
                    ]
                }
            )
        internal_value = super().to_internal_value(data)
        internal_value.update({'make_label': make_label_instance})
        return internal_value


class AssetConditionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.AssetCondition
        fields = ("id", "asset", "notes", "created_at")

    def to_representation(self, instance):
        instance_data = super().to_representation(instance)
        serial_no = instance.asset.serial_number
        asset_code = instance.asset.asset_code
        instance_data['asset'] = f"{serial_no} - {asset_code}"
        return instance_data


class AssetMakeSerializer(serializers.ModelSerializer):
    asset_type = serializers.SerializerMethodField()

    class Meta:
        model = models.AssetMake
        fields = ('id', 'make_label', 'asset_type', 'created_at', 'last_modified_at')

    def get_asset_type(self, obj):
        return obj.asset_type.asset_type

    def to_internal_value(self, data):
        asset_type = data['asset_type']
        if not asset_type:
            raise serializers.ValidationError(
                {'asset_type': [self.error_messages['required']]}
            )
        try:
            asset_type_instance = models.AssetType.objects.get(id=asset_type)
        except Exception:
            raise serializers.ValidationError(
                {
                    'asset_type': [
                        f'Invalid pk \"{asset_type}\" - object does not exist.'
                    ]
                }
            )
        internal_value = super().to_internal_value(data)
        internal_value.update({'asset_type': asset_type_instance})
        return internal_value


class AssetIncidentReportSerializer(serializers.ModelSerializer):
    submitted_by = serializers.SerializerMethodField()

    class Meta:
        model = models.AssetIncidentReport
        fields = (
            'id',
            'asset',
            'incident_type',
            'incident_location',
            'incident_description',
            'injuries_sustained',
            'loss_of_property',
            'witnesses',
            'submitted_by',
            'police_abstract_obtained',
        )

    def get_submitted_by(self, instance):
        if instance.submitted_by:
            return instance.submitted_by.email
        return instance.submitted_by

    def to_representation(self, instance):
        instance_data = super().to_representation(instance)
        serial_no = instance.asset.serial_number
        asset_code = instance.asset.asset_code
        instance_data['asset'] = f"{serial_no} - {asset_code}"
        return instance_data


class AssetHealthSerializer(serializers.ModelSerializer):
    asset_type = serializers.SerializerMethodField()
    model_number = serializers.SerializerMethodField()
    count_by_status = serializers.SerializerMethodField()

    class Meta:
        model = models.Asset
        fields = ('asset_type', 'model_number', 'count_by_status')

    def get_asset_type(self, obj):
        return obj.model_number.make_label.asset_type.asset_type

    def get_count_by_status(self, obj):
        return obj.current_status

    def get_model_number(self, obj):
        return obj.model_number.model_number


class AssetSpecsSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.AssetSpecs
        fields = (
            'id',
            'year_of_manufacture',
            'processor_speed',
            'screen_size',
            'processor_type',
            'storage',
            'memory',
        )
        extra_kwargs = {
            'processor_speed': {'required': False},
            'processor_type': {'required': False},
            'screen_size': {'required': False},
            'memory': {'required': False},
            'storage': {'required': False},
            'year_of_manufacture': {'required': False},
        }
        validators = []

    def validate(self, fields):
        not_unique = models.AssetSpecs.objects.filter(**fields).exists()
        if not_unique:
            raise serializers.ValidationError(
                "Similar asset specification already exist"
            )
        return fields
