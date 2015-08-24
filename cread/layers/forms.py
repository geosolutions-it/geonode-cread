# -*- coding: utf-8 -*-

import autocomplete_light

from geonode.layers.forms import LayerForm
from geonode.layers.models import Layer
from geonode.base.forms import ResourceBaseForm

from django.utils.translation import ugettext as _

class CReadLayerForm(LayerForm):
    """
    Removes title and abstract from the default LayerForm
    """

    class Meta(ResourceBaseForm.Meta):
        model = Layer
        exclude = LayerForm.Meta.exclude + (
            'title',
            'abstract',
            'is_published')
        widgets = autocomplete_light.get_widgets_dict(Layer)
