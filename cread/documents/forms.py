# -*- coding: utf-8 -*-

from geonode.documents.forms import DocumentForm
from geonode.documents.models import Document
from geonode.base.forms import ResourceBaseForm


class CReadDocumentForm(DocumentForm):
    """
    Removes title and abstract from the default DocumentForm
    """

    class Meta(ResourceBaseForm.Meta):
        model = Document
        exclude = DocumentForm.Meta.exclude + (
            'title',
            'abstract')
