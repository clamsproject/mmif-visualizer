from spacy import displacy
from clams import MediaTypes, Annotation
from clams import Mmif
from lapps.discriminators import Uri


def get_displacy(mmif: Mmif):
    return displacy_dict_to_ent_html(mmif_to_displacy_dict(mmif))


def mmif_to_displacy_dict(mmif: Mmif):
    transcript_location = mmif.get_medium_location(MediaTypes.T)
    displacy_dict = {}
    ne_view = mmif.get_view_contains(Uri.NE)
    with open(transcript_location) as transcript_file:
        displacy_dict['text'] = transcript_file.read()
        displacy_dict['ents'] = [displacy_entity(ann) for ann in ne_view.annotations if ann.attype == Uri.NE]
        displacy_dict['title'] = None
    print(displacy_dict)
    return displacy_dict


def displacy_entity(annotation: Annotation):
    return {'start': annotation.start, 'end': annotation.end, 'label': annotation.feature['category']}


def displacy_dict_to_ent_html(d):
    return displacy.render(d, style='ent', manual=True)

