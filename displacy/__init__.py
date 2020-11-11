from spacy import displacy

from mmif.serialize import *
from mmif.vocabulary import AnnotationTypes
from mmif.vocabulary import DocumentTypes
from lapps.discriminators import Uri


def get_displacy(mmif: Mmif):
    return displacy_dict_to_ent_html(mmif_to_displacy_dict(mmif))


def mmif_to_displacy_dict(mmif: Mmif):
    # TODO: this is hard-coded to a transcript in the documents list, should be
    # to a TextDocument in the views or a set of TextDocuments in the views.
    transcript_location = None
    for document in mmif.documents:
        if document.at_type.endswith('TextDocument'):
            transcript_location = document.location
    transcript_location = transcript_location
    displacy_dict = {}
    ne_view = mmif.get_view_contains(Uri.NE)
    with open(transcript_location) as transcript_file:
        displacy_dict['title'] = None
        displacy_dict['text'] = transcript_file.read()
        displacy_dict['ents'] = []
        for ann in ne_view['annotations']:
            if ann.at_type == Uri.NE:
                displacy_dict['ents'].append(entity(ann))
    return displacy_dict


def entity(annotation: Annotation):
    return {'start': annotation.properties['start'],
            'end': annotation.properties['end'],
            'label': annotation.properties['category']}


def displacy_dict_to_ent_html(d):
    return displacy.render(d, style='ent', manual=True)

