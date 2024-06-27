import os

from lapps.discriminators import Uri
from mmif.serialize import Mmif, View, Annotation
from spacy import displacy


def visualize_ner(mmif: Mmif, view: View, document_id: str, app_root: str) -> str:
    displacy_dict = entity_dict(mmif, view, document_id, app_root)
    return dict_to_html(displacy_dict)


def entity_dict(mmif, view, document_id, app_root):
    """Create and return the displacy entity dictionary from a MMIF object. This
    dictionary is in the format that is needed by the render method. Assumes
    that the view's entities all refer to the same document."""
    doc_idx = get_text_documents(mmif)
    doc = doc_idx.get(document_id)
    text = read_text(doc, app_root)
    displacy_dict = {}
    displacy_dict['title'] = None
    displacy_dict['text'] = text
    displacy_dict['ents'] = []
    for ann in view['annotations']:
        if ann.at_type == Uri.NE:
            displacy_dict['ents'].append(entity(view, ann))
    return displacy_dict


def get_text_documents(mmif):
    """Return a dictionary indexed on document identifiers (with the view identifier
    if needed) with text documents as the values."""
    tds = [d for d in mmif.documents if "TextDocument" in str(d.at_type)]
    tds = {td.id:td for td in tds}
    for view in mmif.views:
        # TODO: add check for TextDocument in metadata.contains (saves time)
        for annotation in view.annotations:
            if "TextDocument" in str(annotation.at_type):
                tds["%s:%s" % (view.id, annotation.id)] = annotation
    return tds


def read_text(textdoc, app_root):
    """Read the text content from the document or the text value."""
    if textdoc.location:
        location = textdoc.location
        # adjust the path (possibly needed when you do not run this in a
        # container, see the comment in html_text() in ../app.py)
        if not os.path.isfile(location):
            if location.startswith('file:///'):
                location = location[7:]
            else:
                # this should not happen anymore, but keeping it anyway
                location = location[1:]
            # location = os.path.join(app_root, 'static', location)
        with open(location) as fh:
            text = fh.read()
    else:
        text = textdoc.properties.text.value
    return text


def mmif_to_dict(mmif: Mmif):
    """Create and return the displacy dictionary from a MMIF object. This
    dictionary is in the format that is needed by the render method."""
    # TODO: this is hard-coded to a transcript in the documents list, should be
    # to a TextDocument in the views or a set of TextDocuments in the views.
    transcript_location = None
    for document in mmif.documents:
        if "TextDocument" in document.at_type:
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
                displacy_dict['ents'].append(entity(ne_view, ann))
    return displacy_dict


def entity(view: View, annotation: Annotation):
    return {'start': annotation.get('start'),
            'end': annotation.get('end'),
            'label': annotation.get('category')}


def dict_to_html(d):
    return displacy.render(d, style='ent', manual=True)

