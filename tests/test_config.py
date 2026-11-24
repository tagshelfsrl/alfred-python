import unittest

from alfred.base.constants import (
    RESPONSE_TYPE_HEADER_MAPPING,
    EventType,
    FileEvent,
    JobEvent,
)
from alfred.base.config import Configuration
from alfred.base.typed import ResponseType

V1_DEFAULTS = {
    "version": 1,
    "base_url": "https://app.tagshelf.com",
    "realtime_url": "https://sockets.tagshelf.io",
}

# Wire values are a public contract with the Alfred server. Changing one of
# these is a breaking change, so the table is pinned on purpose.
EVENT_TYPE_WIRE_VALUES = {
    "JOB_EVENT": "job_event",
    "FILE_EVENT": "file_event",
}

FILE_EVENT_WIRE_VALUES = {
    "FILE_ADD_TO_JOB_EVENT": "file_add_to_job_event",
    "FILE_CATEGORY_CREATE_EVENT": "file_category_create_event",
    "FILE_CATEGORY_DELETE_EVENT": "file_category_delete_event",
    "FILE_CHANGE_TAG_EVENT": "file_change_tag_event",
    "FILE_DONE_EVENT": "file_done_event",
    "FILE_EXTRACTED_DATA_CREATE_EVENT": "file_extracted_data_create_event",
    "FILE_EXTRACTED_DATA_DELETE_EVENT": "file_extracted_data_delete_event",
    "FILE_FAILED_EVENT": "file_failed_event",
    "FILE_MOVE_EVENT": "file_move_event",
    "FILE_MOVE_TO_PENDING_EVENT": "file_move_to_pending_event",
    "FILE_MOVE_TO_RECYCLE_BIN_EVENT": "file_move_to_recycle_bin_event",
    "FILE_PROPERTY_CREATE_EVENT": "file_property_create_event",
    "FILE_PROPERTY_DELETE_EVENT": "file_property_delete_event",
    "FILE_REMOVE_TAG_EVENT": "file_remove_tag_event",
    "FILE_STATUS_UPDATE_EVENT": "file_status_update_event",
    "FILE_UPDATE_EVENT": "file_update_event",
}

JOB_EVENT_WIRE_VALUES = {
    "JOB_CREATE_EVENT": "job_create_event",
    "JOB_EXCEEDED_RETRIES_EVENT": "job_exceeded_retries_event",
    "JOB_FAILED_EVENT": "job_failed_event",
    "JOB_FINISHED_EVENT": "job_finished_event",
    "JOB_INVALID_EVENT": "job_invalid_event",
    "JOB_RETRY_EVENT": "job_retry_event",
    "JOB_STAGE_UPDATE_EVENT": "job_stage_update_event",
    "JOB_START_EVENT": "job_start_event",
}


class TestConfigurationDefault(unittest.TestCase):
    def test_default_returns_v1_configuration(self):
        self.assertEqual(Configuration.default(), V1_DEFAULTS)


class TestConfigurationV1(unittest.TestCase):
    def test_v1_without_overrides_uses_production_urls_and_version_1(self):
        self.assertEqual(Configuration.v1(), V1_DEFAULTS)

    def test_v1_with_none_overrides_uses_defaults(self):
        self.assertEqual(Configuration.v1(None), V1_DEFAULTS)

    def test_v1_base_url_override_replaces_only_base_url(self):
        config = Configuration.v1({"base_url": "https://staging.example.test"})

        self.assertEqual(config["base_url"], "https://staging.example.test")
        self.assertEqual(config["realtime_url"], "https://sockets.tagshelf.io")
        self.assertEqual(config["version"], 1)

    def test_v1_realtime_url_override_replaces_only_realtime_url(self):
        config = Configuration.v1({"realtime_url": "https://sockets.example.test"})

        self.assertEqual(config["realtime_url"], "https://sockets.example.test")
        self.assertEqual(config["base_url"], "https://app.tagshelf.com")


class TestEventWireValues(unittest.TestCase):
    def test_event_type_members_and_wire_values_are_pinned(self):
        self.assertEqual(
            {member.name: member.value for member in EventType},
            EVENT_TYPE_WIRE_VALUES,
        )

    def test_file_event_members_and_wire_values_are_pinned(self):
        self.assertEqual(
            {member.name: member.value for member in FileEvent},
            FILE_EVENT_WIRE_VALUES,
        )

    def test_job_event_members_and_wire_values_are_pinned(self):
        self.assertEqual(
            {member.name: member.value for member in JobEvent},
            JOB_EVENT_WIRE_VALUES,
        )


class TestResponseTypeHeaderMapping(unittest.TestCase):
    def test_maps_each_response_type_to_its_content_type(self):
        self.assertEqual(
            RESPONSE_TYPE_HEADER_MAPPING,
            {
                ResponseType.JSON: "application/json",
                ResponseType.TEXT: "text/plain",
                ResponseType.XML: "application/xml",
            },
        )


if __name__ == "__main__":
    unittest.main()
