# -*- coding: UTF-8 -*-
import os
import csv

from datetime import datetime
from tqdm import tqdm

from django.conf import settings
from django.apps import apps

from core.models.asset import Asset


SKIPPED_ROWS = []


def read_csv_row_value(header_name, row):
    value = row.get(header_name).strip()
    if value:
        return value
    return None


def create_object(collection, parent=None, row=None, row_count=None, **values):
    required_for_import = values.pop("required_for_import")
    obj, success = collection_bootstrap(collection, parent, **values)
    if success:
        return obj
    if required_for_import:
        record_errors(row, row_count, obj)


def record_errors(row, row_count, object_error):
    for line in SKIPPED_ROWS:
        if line.get("Row") == row_count:
            line["Error"] += object_error
            return
    row["Error"] = object_error
    row["Row"] = row_count
    SKIPPED_ROWS.append(row)


def write_skipped_records(records, custom_name=None):
    fieldnames = (
        "Row",
        "Category",
        "Sub-Category",
        "Type",
        "Make",
        "Model Number",
        "Asset Code",
        "Serial No.",
        "Assigned To",
        "Status",
        "Memory",
        "Verified",
        "Storage",
        "Processor Type",
        "YOM",
        "Notes",
        "Error",
    )
    timestamp = '{:%Y-%b-%d_%H:%M:%S}'.format(datetime.now())
    file_location = "skipped_assets/skipped_{}.csv".format(timestamp)
    if custom_name:
        file_location = "skipped_assets/{}_{}.csv".format(custom_name, timestamp)
    skipped_records_file_path = os.path.join(settings.BASE_DIR, file_location)
    with open(skipped_records_file_path, "w+") as skipped_file:
        writer = csv.DictWriter(
            skipped_file, delimiter=",", fieldnames=fieldnames)
        writer.writeheader()
        for row in records:
            row["Error"] = set(row["Error"])
            del(row[""])
            writer.writerow(row)
    return file_location


def collection_bootstrap(collection, parent=None, **fields):
    if parent is not None:
        missing_parent = [a for a, b in parent.items() if not b]
        if len(missing_parent) > 0:
            return missing_parent, False
    collection = apps.get_model("core", collection)
    missing_fields = [a for a, b in fields.items() if not b]

    if missing_fields and collection is not Asset:
        return missing_fields, False

    if collection is Asset and len(missing_fields) > 1:
        return missing_fields, False
    return load_to_db(collection, parent, **fields)


def load_to_db(collection, parent=None, **fields):  # noqa: C901
    try:
        obj = collection.objects.get(**fields)
        if collection is Asset:
            return (
                ["Asset with similar asset code or serial number already imported"],
                False,
            )
        return obj, True
    except Exception:
        try:
            if parent:
                return collection.objects.create(**fields, **parent), True
            else:
                return collection.objects.create(**fields), True
        except Exception as e:
            return [str(e)], False
    return "error creating {}".format(collection), False


def process_file_data(csv_reader, custom_name=None, file_length=None):  # noqa: C901
    if file_length:
        progress = tqdm(total=file_length)
    for row_id, row in enumerate(csv_reader):
        if file_length:
            progress.update()
        row_data = {
            "row": row,
            "row_count": row_id,
            "required_for_import": True,
        }
        category_value = read_csv_row_value("Category", row)
        category = create_object(
            "AssetCategory", category_name=category_value, **row_data
        )

        subcategory_value = read_csv_row_value("Sub-Category", row)
        subcategory = create_object(
            "AssetSubCategory",
            parent={"asset_category": category},
            sub_category_name=subcategory_value,
            **row_data,
        )

        type_value = read_csv_row_value("Type", row)
        asset_type = create_object(
            "AssetType",
            parent={"asset_sub_category": subcategory},
            asset_type=type_value,
            **row_data,
        )

        make_value = read_csv_row_value("Make", row)
        asset_make = create_object(
            "AssetMake",
            parent={"asset_type": asset_type},
            make_label=make_value,
            **row_data,
        )

        modelnumber_value = read_csv_row_value("Model Number", row)
        asset_model_no = create_object(
            "AssetModelNumber",
            parent={"make_label": asset_make},
            model_number=modelnumber_value,
            **row_data,
        )

        assetcode_value = read_csv_row_value("Asset Code", row)
        serialnumber_value = read_csv_row_value("Serial No.", row)

        asset_fields = {
            "asset_code": assetcode_value,
            "serial_number": serialnumber_value,
        }
        asset = create_object(
            "Asset",
            parent={"model_number": asset_model_no},
            **row_data,
            **asset_fields,
        )
        if asset:
            row_data["required_for_import"] = False

            asset_verified_value = read_csv_row_value("Verified", row)
            asset_verified_value = (True, False)[
                asset_verified_value == "No"
            ]
            asset.verified = asset_verified_value
            asset.save()

            assigned_to_email_value = read_csv_row_value(
                "Assigned To", row)
            if assigned_to_email_value:
                asset_user = create_object(
                    "User", email=assigned_to_email_value, **row_data
                )

                create_object(
                    "AllocationHistory",
                    parent={"asset": asset},
                    current_owner=asset_user.assetassignee,
                    **row_data,
                )

            asset_status_value = read_csv_row_value("Status", row)
            if asset_status_value:
                create_object(
                    "AssetStatus",
                    parent={"asset": asset},
                    current_status=asset_status_value,
                    **row_data,
                )

            asset_condition_notes_value = read_csv_row_value(
                "Notes", row)
            if asset_condition_notes_value:
                create_object(
                    "AssetCondition",
                    parent={"asset": asset},
                    notes=asset_condition_notes_value,
                    **row_data,
                )

            spec_memory_value = read_csv_row_value("Memory", row)
            spec_storage_value = read_csv_row_value("Storage", row)
            spec_processor_type_value = read_csv_row_value(
                "Processor Type", row
            )
            spec_year_of_manufacture_value = read_csv_row_value(
                "YOM", row)

            spec_data = (
                spec_memory_value
                or spec_storage_value
                or spec_processor_type_value
                or spec_year_of_manufacture_value
            )

            if spec_data:
                asset_spec = create_object(
                    "AssetSpecs",
                    memory=spec_memory_value,
                    storage=spec_storage_value,
                    processor_type=spec_processor_type_value,
                    year_of_manufacture=spec_year_of_manufacture_value,
                    **row_data,
                )
                asset.specs = asset_spec
                asset.save()
    results = {}
    if SKIPPED_ROWS:
        results['skipped'] = write_skipped_records(SKIPPED_ROWS, custom_name=custom_name)
    return results
