from alfred.http.typed import ResponseType

# Response type/header mapping
RESPONSE_TYPE_HEADER_MAPPING = {
    ResponseType.JSON: "application/json",
    ResponseType.TEXT: "text/plain",
    ResponseType.XML: "application/xml",
}
