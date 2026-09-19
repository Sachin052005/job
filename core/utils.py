import uuid
from pathlib import Path


class UploadTo:
    """Deconstructible upload_to callable so migrations can serialize it by subfolder name."""

    def __init__(self, subfolder):
        self.subfolder = subfolder

    def __call__(self, instance, filename):
        ext = Path(filename).suffix.lower()
        return f"{self.subfolder}/{uuid.uuid4().hex}{ext}"

    def __eq__(self, other):
        return isinstance(other, UploadTo) and self.subfolder == other.subfolder

    def deconstruct(self):
        return ("core.utils.UploadTo", [self.subfolder], {})


def unique_upload_path(subfolder):
    return UploadTo(subfolder)
