import json

from clams import Mmif, MediaTypes, Annotation
from lapps.discriminators import Uri

from .brat_configs import config


def mmif_to_brat(mmif: Mmif, attype):
    view = mmif.get_view_contains(attype)
    if view:
        text_fp = open("static" + mmif.get_medium_location(MediaTypes.T)[6:])
        text = text_fp.read()
        text_fp.close()
        doc_data = {'text': text}
        doc_data['entities'] = [brat_entity(ann) for ann in view.annotations if ann.attype == Uri.NE]
        return json.dumps(doc_data)
    else:
        return ""


def brat_entity(ann: Annotation):
    # TODO (krim @ 9/29/19): hardcoding "category" feature name should be fixed in the future
    return [ann.id, ann.feature["category"], [ [ann.start, ann.end + 10] ] ]




