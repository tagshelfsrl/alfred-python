import os
import tempfile
import unittest
from io import BytesIO
from unittest.mock import patch

from alfred.base.exceptions import AlfredMissingArgument
from alfred.rest.files import FilesFactory
from alfred.rest.files.v1 import Files


class RecordingHttpClient:
    """
    Records every get/post call as (uri, params, data, files, headers)
    and answers with a scripted (parsed, response) tuple.
    """

    def __init__(self, get_result=(None, None), post_result=(None, None)):
        self.get_result = get_result
        self.post_result = post_result
        self.get_calls = []
        self.post_calls = []

    def get(self, uri, params=None, data=None, headers=None, files=None, timeout=None):
        self.get_calls.append((uri, params, data, files, headers))
        return self.get_result

    def post(self, uri, params=None, data=None, headers=None, files=None, timeout=None):
        self.post_calls.append((uri, params, data, files, headers))
        return self.post_result


class FakeResponse:
    def __init__(self, content=b"", headers=None):
        self.content = content
        self.headers = headers or {}


class TestFilesGetAndUpload(unittest.TestCase):
    def test_get_requests_file_detail_route(self):
        client = RecordingHttpClient(get_result=({"id": "f1"}, None))

        Files(client).get("f1")

        self.assertEqual(client.get_calls, [("/api/file/detail/f1", None, None, None, None)])

    def test_get_returns_parsed_body(self):
        client = RecordingHttpClient(get_result=({"id": "f1", "file_name": "a.pdf"}, None))

        result = Files(client).get("f1")

        self.assertEqual(result, {"id": "f1", "file_name": "a.pdf"})

    def test_upload_posts_payload_as_data_to_upload_route(self):
        payload = {"url": "https://example.com/a.pdf", "container": "c1"}
        client = RecordingHttpClient(post_result=({"file_id": "f1"}, None))

        Files(client).upload(payload)

        self.assertEqual(client.post_calls, [("/api/file/upload", None, payload, None, None)])

    def test_upload_returns_parsed_response(self):
        client = RecordingHttpClient(post_result=({"file_id": "f1"}, None))

        result = Files(client).upload({"url": "https://example.com/a.pdf"})

        self.assertEqual(result, {"file_id": "f1"})


class TestFilesDownload(unittest.TestCase):
    def _download(self, content_disposition, content=b"%PDF-1.4", content_type="application/pdf"):
        headers = {"Content-Type": content_type}
        if content_disposition is not None:
            headers["Content-Disposition"] = content_disposition
        client = RecordingHttpClient(get_result=(None, FakeResponse(content, headers)))
        result = Files(client).download("f1")
        return result, client

    def test_download_requests_download_route(self):
        _, client = self._download('attachment; filename="a.pdf"')

        self.assertEqual(client.get_calls, [("/api/file/download/f1", None, None, None, None)])

    def test_download_returns_response_bytes_in_bytesio(self):
        result, _ = self._download('attachment; filename="a.pdf"', content=b"%PDF-1.4 body")

        self.assertIsInstance(result["file"], BytesIO)
        self.assertEqual(result["file"].getvalue(), b"%PDF-1.4 body")

    def test_download_returns_content_type_as_mime_type(self):
        result, _ = self._download('attachment; filename="a.pdf"', content_type="image/png")

        self.assertEqual(result["mime_type"], "image/png")

    def test_download_returns_none_name_for_bare_attachment_disposition(self):
        result, _ = self._download("attachment")

        self.assertIsNone(result["original_name"])

    def test_download_returns_none_name_when_content_disposition_header_is_absent(self):
        # BUG: crashes with TypeError on the unmodified code.
        result, _ = self._download(None)

        self.assertIsNone(result["original_name"])
        self.assertEqual(result["mime_type"], "application/pdf")

    def test_download_reads_quoted_filename(self):
        result, _ = self._download('attachment; filename="report.pdf"')

        self.assertEqual(result["original_name"], "report.pdf")

    def test_download_reads_unquoted_filename(self):
        result, _ = self._download("attachment; filename=report.pdf")

        self.assertEqual(result["original_name"], "report.pdf")

    def test_download_drops_trailing_parameters_after_quoted_filename(self):
        # BUG: returns 'report.pdf"; size=123' on the unmodified code.
        result, _ = self._download('attachment; filename="report.pdf"; size=123')

        self.assertEqual(result["original_name"], "report.pdf")

    def test_download_decodes_rfc5987_filename_star(self):
        result, _ = self._download("attachment; filename*=UTF-8''informe%20final.pdf")

        self.assertEqual(result["original_name"], "informe final.pdf")

    def test_download_decodes_utf8_percent_encoded_filename_star(self):
        result, _ = self._download("attachment; filename*=UTF-8''na%C3%AFve.pdf")

        self.assertEqual(result["original_name"], "naïve.pdf")

    def test_download_prefers_encoded_filename_when_both_forms_are_present(self):
        # RFC 6266, section 4.3: `filename*` wins over `filename`.
        result, _ = self._download(
            "attachment; filename=\"fallback.pdf\"; filename*=UTF-8''real%20name.pdf"
        )

        self.assertEqual(result["original_name"], "real name.pdf")

    def test_download_prefers_encoded_filename_whatever_the_parameter_order(self):
        result, _ = self._download(
            "attachment; filename*=UTF-8''real%20name.pdf; filename=\"fallback.pdf\""
        )

        self.assertEqual(result["original_name"], "real name.pdf")

    def test_download_decodes_filename_star_in_a_non_utf8_charset(self):
        result, _ = self._download("attachment; filename*=iso-8859-1'en'%A3%20rates.pdf")

        self.assertEqual(result["original_name"], "\u00a3 rates.pdf")

    def test_download_keeps_semicolon_inside_quoted_filename(self):
        result, _ = self._download("inline; filename=\"a;b.pdf\"")

        self.assertEqual(result["original_name"], "a;b.pdf")

    def test_download_keeps_non_ascii_characters_of_plain_filename(self):
        result, _ = self._download("attachment; filename=\"informe a\u00f1o.pdf\"")

        self.assertEqual(result["original_name"], "informe a\u00f1o.pdf")

    def test_download_reads_filename_whatever_the_parameter_case(self):
        result, _ = self._download("ATTACHMENT; FILENAME=\"Upper.PDF\"")

        self.assertEqual(result["original_name"], "Upper.PDF")

    def test_download_uses_first_plain_filename_when_it_is_repeated(self):
        result, _ = self._download(
            "attachment; filename=\"first.pdf\"; filename=\"second.pdf\""
        )

        self.assertEqual(result["original_name"], "first.pdf")

    def test_download_returns_none_name_for_empty_filename_values(self):
        for header in ("attachment; filename=\"\"", "attachment; filename*=UTF-8''", ""):
            with self.subTest(header=header):
                result, _ = self._download(header)

                self.assertIsNone(result["original_name"])


class TestFilesUploadFile(unittest.TestCase):
    def setUp(self):
        magic_patcher = patch("alfred.rest.files.v1.magic")
        self.magic = magic_patcher.start()
        self.addCleanup(magic_patcher.stop)
        self.magic.from_buffer.return_value = "application/pdf"

        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

    def _write_temp_file(self, name, content):
        path = os.path.join(self.temp_dir.name, name)
        with open(path, "wb") as handle:
            handle.write(content)
        return path

    def test_upload_file_posts_to_uploadfile_route(self):
        client = RecordingHttpClient(post_result=({"file_id": "f1"}, None))
        payload = {"file": BytesIO(b"abc"), "filename": "doc.pdf", "session_id": "s1"}

        Files(client).upload_file(payload)

        self.assertEqual(len(client.post_calls), 1)
        uri, params, _, _, headers = client.post_calls[0]
        self.assertEqual(uri, "/api/file/uploadfile")
        self.assertIsNone(params)
        self.assertIsNone(headers)

    def test_upload_file_returns_parsed_response(self):
        client = RecordingHttpClient(post_result=({"file_id": "f1"}, None))
        payload = {"file": BytesIO(b"abc"), "filename": "doc.pdf", "session_id": "s1"}

        result = Files(client).upload_file(payload)

        self.assertEqual(result, {"file_id": "f1"})

    def test_upload_file_sends_bytesio_under_given_filename_and_detected_mime_type(self):
        client = RecordingHttpClient()
        file_obj = BytesIO(b"abc")
        payload = {"file": file_obj, "filename": "doc.pdf", "session_id": "s1"}

        Files(client).upload_file(payload)

        _, _, _, files, _ = client.post_calls[0]
        self.assertEqual(files, {"file": ("doc.pdf", file_obj, "application/pdf")})

    def test_upload_file_sends_session_id_and_empty_json_metadata_when_metadata_omitted(self):
        client = RecordingHttpClient()
        payload = {"file": BytesIO(b"abc"), "filename": "doc.pdf", "session_id": "s1"}

        Files(client).upload_file(payload)

        _, _, data, _, _ = client.post_calls[0]
        self.assertEqual(data, {"session_id": "s1", "metadata": "{}"})

    def test_upload_file_sends_metadata_as_json_string(self):
        client = RecordingHttpClient()
        payload = {
            "file": BytesIO(b"abc"),
            "filename": "doc.pdf",
            "session_id": "s1",
            "metadata": {"owner": "raul"},
        }

        Files(client).upload_file(payload)

        _, _, data, _, _ = client.post_calls[0]
        self.assertEqual(data, {"session_id": "s1", "metadata": '{"owner": "raul"}'})

    def test_upload_file_raises_missing_argument_for_bytesio_without_filename(self):
        client = RecordingHttpClient()
        payload = {"file": BytesIO(b"abc"), "filename": None, "session_id": "s1"}

        with self.assertRaises(AlfredMissingArgument):
            Files(client).upload_file(payload)

        self.assertEqual(client.post_calls, [])

    def test_upload_file_detects_mime_type_from_first_kilobyte(self):
        client = RecordingHttpClient()
        content = b"x" * 2048
        payload = {"file": BytesIO(content), "filename": "doc.pdf", "session_id": "s1"}

        Files(client).upload_file(payload)

        self.magic.from_buffer.assert_called_once_with(content[:1024], mime=True)

    def test_upload_file_rewinds_bytesio_before_sending(self):
        client = RecordingHttpClient()
        file_obj = BytesIO(b"x" * 2048)
        payload = {"file": file_obj, "filename": "doc.pdf", "session_id": "s1"}

        Files(client).upload_file(payload)

        self.assertEqual(file_obj.tell(), 0)

    def test_upload_file_uses_basename_of_real_file_instead_of_payload_filename(self):
        client = RecordingHttpClient()
        path = self._write_temp_file("invoice.pdf", b"%PDF-1.4 real bytes")

        with open(path, "rb") as handle:
            payload = {"file": handle, "filename": "other.txt", "session_id": "s1"}
            Files(client).upload_file(payload)

        _, _, _, files, _ = client.post_calls[0]
        self.assertEqual(files["file"][0], "invoice.pdf")

    def test_upload_file_rewinds_real_file_before_sending(self):
        client = RecordingHttpClient()
        path = self._write_temp_file("invoice.pdf", b"x" * 2048)

        with open(path, "rb") as handle:
            payload = {"file": handle, "filename": None, "session_id": "s1"}
            Files(client).upload_file(payload)
            self.assertEqual(handle.tell(), 0)

        _, _, _, files, _ = client.post_calls[0]
        self.assertEqual(files["file"][1].name, path)

    def test_upload_file_sends_real_file_object_itself(self):
        client = RecordingHttpClient()
        path = self._write_temp_file("invoice.pdf", b"%PDF-1.4")

        with open(path, "rb") as handle:
            payload = {"file": handle, "filename": None, "session_id": "s1"}
            Files(client).upload_file(payload)
            _, _, _, files, _ = client.post_calls[0]
            self.assertIs(files["file"][1], handle)


class TestFilesFactory(unittest.TestCase):
    def test_create_version_1_returns_files_bound_to_http_client(self):
        client = RecordingHttpClient()

        result = FilesFactory.create(1, client)

        self.assertIsInstance(result, Files)
        self.assertIs(result.http_client, client)

    def test_create_unsupported_version_raises_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            FilesFactory.create(2, RecordingHttpClient())

        self.assertEqual(str(ctx.exception), "Unsupported version: 2")


if __name__ == "__main__":
    unittest.main()
