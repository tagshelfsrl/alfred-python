import unittest

from alfred.base.constants import LEGACY_EVENT_NAMES, FileEvent, JobEvent

EXPECTED_FILE_EVENTS = {
    "FILE_CREATE_EVENT": "alfred_event_file_create",
    "FILE_ADD_TO_JOB_EVENT": "alfred_event_file_added_to_job",
    "FILE_CATEGORY_CREATE_EVENT": "alfred_event_file_category_create",
    "FILE_CATEGORY_DELETE_EVENT": "alfred_event_file_category_delete",
    "FILE_CHANGE_TAG_EVENT": "alfred_event_file_change_tag",
    "FILE_DECOMPOSED_EVENT": "alfred_event_file_decomposed",
    "FILE_DONE_EVENT": "alfred_event_file_done",
    "FILE_EXTRACTED_DATA_CREATE_EVENT": "alfred_event_file_extracted_data_create",
    "FILE_EXTRACTED_DATA_DELETE_EVENT": "alfred_event_file_extracted_data_delete",
    "FILE_FAILED_EVENT": "alfred_event_file_failed",
    "FILE_MOVE_EVENT": "alfred_event_file_move",
    "FILE_MOVE_TO_DECOMPOSED_EVENT": "alfred_event_file_move_to_decomposed",
    "FILE_MOVE_TO_PENDING_EVENT": "alfred_event_file_move_to_pending",
    "FILE_MOVE_TO_RECYCLE_BIN_EVENT": "alfred_event_file_move_to_recycle_bin",
    "FILE_PROPERTY_CREATE_EVENT": "alfred_event_file_property_create",
    "FILE_PROPERTY_DELETE_EVENT": "alfred_event_file_property_delete",
    "FILE_REMOVE_TAG_EVENT": "alfred_event_file_change_tag",
    "FILE_STATUS_UPDATE_EVENT": "alfred_event_file_status_update",
    "FILE_UPDATE_EVENT": "alfred_event_file_update",
}

EXPECTED_JOB_EVENTS = {
    "JOB_CREATE_EVENT": "alfred_event_job_create",
    "JOB_START_EVENT": "alfred_event_job_start",
    "JOB_STAGE_UPDATE_EVENT": "alfred_event_job_stage_update",
    "JOB_RETRY_EVENT": "alfred_event_job_retry",
    "JOB_EXCEEDED_RETRIES_EVENT": "alfred_event_job_retry",
    "JOB_INVALID_EVENT": "alfred_event_job_invalid",
    "JOB_FAILED_EVENT": "alfred_event_job_failed",
    "JOB_CANCELLED_EVENT": "alfred_event_job_cancelled",
    "JOB_EXPIRED_EVENT": "alfred_event_job_expired",
    "JOB_FINISHED_EVENT": "alfred_event_job_finished",
}


class TestEventConstants(unittest.TestCase):
    def test_file_event_members_have_the_names_alfred_sends(self):
        self.assertEqual({n: m.value for n, m in FileEvent.__members__.items()}, EXPECTED_FILE_EVENTS)

    def test_job_event_members_have_the_names_alfred_sends(self):
        self.assertEqual({n: m.value for n, m in JobEvent.__members__.items()}, EXPECTED_JOB_EVENTS)

    def test_remove_tag_is_an_alias_of_change_tag(self):
        self.assertIs(FileEvent.FILE_REMOVE_TAG_EVENT, FileEvent.FILE_CHANGE_TAG_EVENT)

    def test_exceeded_retries_is_an_alias_of_retry(self):
        self.assertIs(JobEvent.JOB_EXCEEDED_RETRIES_EVENT, JobEvent.JOB_RETRY_EVENT)

    def test_legacy_names_has_24_entries(self):
        self.assertEqual(len(LEGACY_EVENT_NAMES), 24)

    def test_every_legacy_name_ends_in_event(self):
        for name in LEGACY_EVENT_NAMES:
            self.assertTrue(name.endswith("_event"), name)

    def test_every_legacy_name_maps_to_the_value_of_an_enum_member(self):
        values = {m.value for e in (FileEvent, JobEvent) for m in e}
        for name, target in LEGACY_EVENT_NAMES.items():
            self.assertIn(target, values, name)

    def test_legacy_names_follow_the_naming_rule_except_for_three_exceptions(self):
        exceptions = {
            "file_add_to_job_event": "alfred_event_file_added_to_job",
            "file_remove_tag_event": "alfred_event_file_change_tag",
            "job_exceeded_retries_event": "alfred_event_job_retry",
        }
        for name, target in LEGACY_EVENT_NAMES.items():
            expected = exceptions.get(name, "alfred_event_" + name[: -len("_event")])
            self.assertEqual(target, expected, name)

    def test_stream_names_are_not_legacy_names(self):
        self.assertNotIn("job_event", LEGACY_EVENT_NAMES)
        self.assertNotIn("file_event", LEGACY_EVENT_NAMES)
