import datetime
import json
import tempfile
from typing import Dict

import mmif
from flask import url_for
from mmif import AnnotationTypes, DocumentTypes, Mmif
from mmif.utils import video_document_helper as vdh

import cache
import utils


def generate_iiif_manifest(in_mmif: mmif.Mmif, viz_id):
    iiif_json = {
        "@context": "http://iiif.io/api/presentation/2/context.json",
        "id": "http://0.0.0.0:5000/mmif_example_manifest.json",
        "type": "Manifest",
        "label": "NewsHour Sample",
        "description": f"generated at {datetime.datetime.now()}",
        "sequences": [
            {
                "id": f"http://0.0.0.0:5000/mmif_example_manifest.json/sequence/1",
                "type": "Sequence",
                "canvases": [],
            }
        ],
        "structures": []
    }
    add_canvas_from_documents(viz_id, in_mmif, iiif_json)
    add_structure_from_timeframe(in_mmif, iiif_json)
    return save_manifest(iiif_json, viz_id)


def add_canvas_from_documents(viz_id, in_mmif, iiif_json):
    video_documents = in_mmif.get_documents_by_type(DocumentTypes.VideoDocument)
    audio_documents = in_mmif.get_documents_by_type(DocumentTypes.AudioDocument)
    image_documents = in_mmif.get_documents_by_type(DocumentTypes.ImageDocument)
    all_documents = video_documents + audio_documents + image_documents
    document_canvas_dict = {}
    for _id, document in enumerate(all_documents, start=1):
        canvas_media_path = url_for(
            'static', filename=f"{cache._CACHE_DIR_SUFFIX}/{viz_id}/{utils.get_src_media_symlink_basename(document)}")
        document_canvas_dict[document.id] = _id
        canvas = {
            "id": f"http://0.0.0.0:5000/mmif_example_manifest.json/canvas/{_id}",
            "type": "Canvas",
            "label": "NewsHour",
            "height": 360,
            "width": 480,
            "duration": 660,
            "content": [
                {
                    "id": "...",
                    "type": "AnnotationPage",
                    "items": [
                        {
                            "id": "...",
                            "type": "Annotation",
                            "motivation": "painting",
                            "body": [
                                {
                                    "type": "Choice",
                                    "choiceHint": "user",
                                    "items": [
                                        {
                                            "id": canvas_media_path,
                                            "type": get_iiif_type(document),
                                            "label": "",
                                            "format": get_iiif_format(document)
                                        }
                                    ]
                                }
                            ],
                            "target": f"http://0.0.0.0:5000/mmif_example_manifest.json/canvas/{_id}"
                        }
                    ],
                }
            ],
        }
        iiif_json["sequences"][0]["canvases"].append(canvas)
        break # todo currently only supports single document, needs more work to align canvas values


def add_structure_from_timeframe(in_mmif: Mmif, iiif_json: Dict):
    # # get all views with timeframe annotations from mmif obj
    tf_views = in_mmif.get_views_contain(AnnotationTypes.TimeFrame)
    for range_id, view in enumerate(tf_views, start=1):
        view_range = {
            "id": f"http://0.0.0.0:5000/mmif_example_manifest.json/range/{range_id}",
            "type": "Range",
            "label": f"View: {view.id}",
            "members": []
        }
        for ann in view.get_annotations(AnnotationTypes.TimeFrame):
            label = ann.get_property('label')
            s, e = vdh.convert_timeframe(in_mmif, ann, "seconds")

            structure = {
                "id": f"http://0.0.0.0:5000/mmif_example_manifest.json/range/{range_id}",
                "type": "Range",
                "label": f"{label.capitalize()}",
                "members": [
                    {
                        "id": f"http://0.0.0.0:5000/mmif_example_manifest.json/canvas/{1}#t={s},{e}",
                        # need to align id here to support more than one document
                        "type": "Canvas"
                    }
                ]
            }
            view_range["members"].append(structure)
        iiif_json["structures"].append(view_range)


def save_manifest(iiif_json: Dict, viz_id) -> str:
    # generate a iiif manifest and save output file
    manifest = tempfile.NamedTemporaryFile(
        'w', dir=str(cache.get_cache_root() / viz_id), suffix='.json', delete=False)
    json.dump(iiif_json, manifest, indent=4)
    return manifest.name


def get_iiif_format(document):
    if document.is_type(DocumentTypes.VideoDocument):
        return 'video/mp4'
    elif document.is_type(DocumentTypes.ImageDocument):
        return "image/jpeg"
    else:
        raise ValueError("invalid document type for iiif canvas")


def get_iiif_type(document):
    if document.is_type(DocumentTypes.VideoDocument):
        return 'Video'
    elif document.is_type(DocumentTypes.ImageDocument):
        return 'Image'
    else:
        raise ValueError("invalid document type for iiif canvas")
