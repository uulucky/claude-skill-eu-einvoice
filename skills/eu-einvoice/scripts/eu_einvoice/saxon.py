"""One shared Saxon-HE processor (saxonche) and a cache of compiled XSLTs."""

_proc = None
_compiled = {}


def processor():
    global _proc
    if _proc is None:
        try:
            from saxonche import PySaxonProcessor
        except ImportError as e:
            raise RuntimeError(
                "saxonche is not installed. Run: pip install -r requirements.txt "
                "(Schematron validation needs it; XSD checks still work without it)"
            ) from e
        _proc = PySaxonProcessor(license=False)
    return _proc


def run_xslt(xslt_path, xml_path):
    key = str(xslt_path)
    if key not in _compiled:
        _compiled[key] = processor().new_xslt30_processor().compile_stylesheet(stylesheet_file=key)
    return _compiled[key].transform_to_string(source_file=str(xml_path))
