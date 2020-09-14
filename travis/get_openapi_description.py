#!/usr/bin/env python
# python3

from absl import app

from grr_response_server.gui import api_call_router
from grr_response_server.gui.api_plugins import metadata as metadata_plugin


_OPENAPI_DESCRIPTION_FILE_NAME = "travis_openapi_description.json"


def main(argv):
  del argv  # Unused.

  router = api_call_router.ApiCallRouterStub()
  openapi_handler = metadata_plugin.ApiGetOpenApiDescriptionHandler(router)
  openapi_handler_result = openapi_handler.Handle(None)
  openapi_description = openapi_handler_result.openapi_description

  with open(file=_OPENAPI_DESCRIPTION_FILE_NAME, mode="w") as file:
    file.write(openapi_description)


if __name__ == "__main__":
  app.run(main)
