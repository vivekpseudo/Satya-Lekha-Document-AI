from google.api_core.client_options import ClientOptions
from google.cloud import documentai_v1 as documentai


class DocumentAIService:
    def __init__(self, project_id: str, location: str, processor_id: str):
        self.project_id = project_id
        self.location = location
        self.processor_id = processor_id
        self.client = documentai.DocumentProcessorServiceClient(
            client_options=ClientOptions(
                api_endpoint=f"{location}-documentai.googleapis.com"
            )
        )

    def process(self, content: bytes, mime_type: str) -> documentai.Document:
        name = self.client.processor_path(
            self.project_id,
            self.location,
            self.processor_id,
        )
        request = documentai.ProcessRequest(
            name=name,
            raw_document=documentai.RawDocument(
                content=content,
                mime_type=mime_type,
            ),
        )
        response = self.client.process_document(request=request)
        return response.document
