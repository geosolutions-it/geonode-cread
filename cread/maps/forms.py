# -*- coding: utf-8 -*-

from geonode.maps.forms import MapForm
from geonode.maps.models import Map
from geonode.base.forms import ResourceBaseForm
import autocomplete_light


class CReadMapForm(MapForm):
    """
    Removes title and abstract from the default Form
    """

    class Meta(ResourceBaseForm.Meta):
        model = Map
        exclude = MapForm.Meta.exclude + (
            'title',
            'abstract')
        widgets = autocomplete_light.get_widgets_dict(Map)