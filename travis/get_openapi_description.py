#!/usr/bin/env python
# python3

import os

from absl import app

from grr_response_server.gui import api_call_router
from grr_response_server.gui.api_plugins import metadata as metadata_plugin


OPENAPI_JSON_FILE_NAME = os.environ.get(
  "OPENAPI_JSON_FILE_NAME",
  default="travis_openapi_description.json"
)
HOME_PATH = os.environ["HOME"]
OPENAPI_JSON_FILE_PATH = os.path.join(HOME_PATH, OPENAPI_JSON_FILE_NAME)


def main(argv):
  del argv  # Unused.

  router = api_call_router.ApiCallRouterStub()
  openapi_handler = metadata_plugin.ApiGetOpenApiDescriptionHandler(router)
  openapi_handler_result = openapi_handler.Handle(None)
  openapi_description = openapi_handler_result.openapi_description

  with open(file=OPENAPI_JSON_FILE_PATH, mode="w") as file:
    file.write(openapi_description)


if __name__ == "__main__":
  app.run(main)
