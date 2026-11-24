import unittest

from alfred.rest.jobs.v1 import Jobs


class FakeHttpClient:
    def __init__(self, post_response=None, get_response=None):
        self.post_response = post_response
        self.get_response = get_response

    def post(self, *_args, **_kwargs):
        return self.post_response, None

    def get(self, *_args, **_kwargs):
        return self.get_response, None


class TestJobsSmoke(unittest.TestCase):
    def test_create_returns_raw_job_creation_response(self):
        jobs = Jobs(
            FakeHttpClient(
                post_response={
                    "id": "job-1",
                }
            )
        )

        result = jobs.create({})

        self.assertEqual(result, {"id": "job-1"})

    def test_get_normalizes_invalid_job_metadata_to_empty_dict(self):
        jobs = Jobs(
            FakeHttpClient(
                get_response={
                    "id": "job-1",
                    "metadata": "not-json",
                }
            )
        )

        result = jobs.get("job-1")

        self.assertEqual(result.get("metadata"), {})

    def test_get_normalizes_wrapped_single_job_metadata(self):
        jobs = Jobs(
            FakeHttpClient(
                get_response={
                    "result": {
                        "id": "job-1",
                        "metadata": "{\"metadata_key\": \"metadata_value\"}",
                    }
                }
            )
        )

        result = jobs.get("job-1")

        self.assertEqual(
            result.get("result"),
            {"id": "job-1", "metadata": {"metadata_key": "metadata_value"}},
        )

    def test_get_all_normalizes_metadata_in_paginated_results(self):
        jobs = Jobs(
            FakeHttpClient(
                get_response={
                    "result": [
                        {
                            "id": "job-1",
                            "metadata": "{\"metadata_key\": \"metadata_value\"}",
                        },
                        {
                            "id": "job-2",
                            "metadata": "",
                        },
                    ],
                    "total": 2,
                }
            )
        )

        result = jobs.get_all()

        self.assertEqual(
            result.get("result"),
            [
                {"id": "job-1", "metadata": {"metadata_key": "metadata_value"}},
                {"id": "job-2", "metadata": {}},
            ],
        )


if __name__ == "__main__":
    unittest.main()
