__author__ = 'Chuck Martin'

import json
from tempfile import NamedTemporaryFile


def write_secrets(secrets):
    fp = NamedTemporaryFile(delete=False)
    json.dump(secrets, fp)
    fp.close()
    return fp.name
