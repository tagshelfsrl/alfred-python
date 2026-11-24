import unittest

from alfred.base.constants import RESPONSE_TYPE_HEADER_MAPPING, EventType
from alfred.base.config import Configuration
from alfred.base.typed import ResponseType

V1_DEFAULTS = {
    "version": 1,
    "base_url": "https://app.tagshelf.com",
    "realtime_url": "https://sockets.tagshelf.io",
}

# Wire values are a public contract with the Alfred server. Changing one of
# these is a breaking change, so the table is pinned on purpose.
# The names of the single events are pinned in tests/test_constants.py.
EVENT_TYPE_WIRE_VALUES = {
    "JOB_EVENT": "job_event",
    "FILE_EVENT": "file_event",
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
