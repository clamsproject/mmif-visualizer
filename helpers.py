from mmif.serialize.annotation import Text
from flask import current_app
import cache

def url2posix(path):
    """For the visualizer we often want a POSIX path and not a URL so we strip off
    the protocol if there is one."""
    if str(path).startswith('file:///'):
        path = path[7:]
    return path


def get_doc_path(document):
        doc_path = document.location_path()
        return doc_path
        # app.logger.debug(f"MMIF on AV asset: {doc_path}")
        # doc_symlink_path = pathlib.Path(app.static_folder) / cache._CACHE_DIR_SUFFIX / viz_id / (f"{document.id}.{doc_path.split('.')[-1]}")
        # os.symlink(doc_path, doc_symlink_path)
        # app.logger.debug(f"{doc_path} is symlinked to {doc_symlink_path}")
        # doc_symlink_rel_path = '/' + doc_symlink_path.relative_to(app.static_folder).as_posix()
        # app.logger.debug(f"and {doc_symlink_rel_path} will be used in HTML src attribute")


def get_status(view):
    return 'ERROR' if 'message' in view.metadata.error else 'OKAY'


def get_properties(annotation):
    props = annotation.properties._serialize()
    props.pop('id')
    props_list = []
    for prop in sorted(props):
        val = props[prop]
        if type(val) == Text:
            val = val.value
        props_list.append("%s=%s" % (prop, val))
    return '{ %s }' % ', '.join(props_list)


def get_abstract_view_type(view, mmif):
     annotation_types = [a.shortname for a in view.metadata.contains.keys()]
     if "NamedEntity" in annotation_types:
          return "NER"
     elif all([anno_type in annotation_types for anno_type in ["Token", "TimeFrame", "Alignment"]]):
          return "ASR"
    # Define an OCR view as one that refers to a video and doesn't contain Sentences
    # or Tokens
     else:
         for configuration in view.metadata.contains.values():
             if "document" in configuration \
              and mmif.get_document_by_id(configuration["document"]).at_type.shortname == "VideoDocument":
                 if not any([anno_type in annotation_types for anno_type in ["Sentence", "Token"]]):
                     return "OCR"
                 
     

def get_vtt_file(view, viz_id):
    vtt_filename = cache.get_cache_root() / viz_id / f"{view.id.replace(':', '-')}.vtt" 
    if not vtt_filename.exists(): 
        with open(vtt_filename, 'w') as vtt_file:
            vtt_file.write(write_vtt(view, viz_id))
    return str(vtt_filename)


def write_vtt(view, viz_id):
    vtt = "WEBVTT\n\n"
    timeunit = "milliseconds"
    for a in view.metadata.contains.values():
        if "timeUnit" in a:
            timeunit = a["timeUnit"]
            break
    token_idx = {a.id: a for a in view.annotations if a.at_type.shortname == "Token"}
    timeframe_idx = {a.id: a for a in view.annotations if a.at_type.shortname == "TimeFrame"}
    alignments = [a for a in view.annotations if a.at_type.shortname == "Alignment"]
    vtt_start = None
    texts = []
    for alignment in alignments:
        start_end_text = build_alignment(alignment, token_idx, timeframe_idx)
        if start_end_text is None:
            continue
        start, end, text = start_end_text
        if not vtt_start:
            vtt_start = format_time(start, timeunit)
        texts.append(text)
        if len(texts) > 8:
            vtt_end = format_time(end, timeunit)
            vtt += f"{vtt_start} --> {vtt_end}\n{' '.join(texts)}\n\n"
            vtt_start = None
            texts = []
    return vtt


def build_alignment(alignment, token_idx, timeframe_idx):
    target = alignment.properties['target']
    source = alignment.properties['source']
    timeframe = timeframe_idx.get(source)
    token = token_idx.get(target)
    if timeframe and token:
        start = timeframe.properties['start']
        end = timeframe.properties['end']
        text = token.properties['word']
        return start, end, text


def format_time(time, unit):
    """
    Formats a time in seconds as a string in the format "hh:mm:ss.fff"
    VTT specifically requires timestamps expressed in miliseconds and
    must be be in one of these formats: mm:ss.ttt or hh:mm:ss.ttt
    (https://developer.mozilla.org/en-US/docs/Web/API/WebVTT_API)
    ISO format can have up to 6 below the decimal point, on the other hand
    """
    if unit == "seconds":
        time_in_ms = int(time * 1000)
    else:
        time_in_ms = int(time)
    hours = time_in_ms // (1000 * 60 * 60)
    time_in_ms %= (1000 * 60 * 60)
    minutes = time_in_ms // (1000 * 60)
    time_in_ms %= (1000 * 60)
    seconds = time_in_ms // 1000
    time_in_ms %= 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{time_in_ms:03d}"