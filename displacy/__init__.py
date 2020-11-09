from spacy import displacy
from clams import MediaTypes, Annotation
from clams import Mmif
from lapps.discriminators import Uri


def get_displacy(mmif: Mmif):
    return displacy_dict_to_ent_html(mmif_to_displacy_dict(mmif))


def mmif_to_displacy_dict(mmif: Mmif):
    # NOTE: location was not following the requirement to be where advertized
    transcript_location = mmif.get_medium_location(MediaTypes.T)
    transcript_location = '/mmif-viz/static/' + transcript_location
    displacy_dict = {}
    # not sure why this one breaks, for now hardcoding it
    # ne_view = mmif.get_view_contains(Uri.NE)
    ne_view = mmif.views[0]
    with open(transcript_location) as transcript_file:
        displacy_dict['text'] = transcript_file.read()
        # NOTE: this was a dictionary, not an object
        # displacy_dict['ents'] = [displacy_entity(ann) for ann in ne_view.annotations if ann.attype == Uri.NE]
        displacy_dict['ents'] = [displacy_entity(ann) for ann in ne_view['annotations'] if ann["@type"] == Uri.NE]
        displacy_dict['title'] = None
    return displacy_dict


def displacy_entity(annotation: Annotation):
    # NOTE: this is a dictionary
    # return {'start': annotation.start, 'end': annotation.end, 'label': annotation.feature['category']}
    return {'start': annotation['start'], 'end': annotation['end'], 'label': annotation['feature']['category']}


def displacy_dict_to_ent_html(d):
    return displacy.render(d, style='ent', manual=True)

