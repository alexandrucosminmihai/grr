#!/usr/bin/env python
# Lint as: python3
"""A module with API methods related to the GRR metadata."""
import json
import inspect

from urllib import parse as urlparse
from typing import Optional

from grr_response_core import version
from grr_response_core.lib.rdfvalues import structs as rdf_structs
from grr_response_proto.api import metadata_pb2
from grr_response_server import access_control
from grr_response_server.gui import api_call_handler_base


class ApiGetGrrVersionResult(rdf_structs.RDFProtoStruct):
  """An RDF wrapper for result of the API method for getting GRR version."""

  protobuf = metadata_pb2.ApiGetGrrVersionResult
  rdf_deps = []


class ApiGetGrrVersionHandler(api_call_handler_base.ApiCallHandler):
  """An API handler for the API method for getting GRR version."""

  result_type = ApiGetGrrVersionResult

  def Handle(
      self,
      args: None,
      token: Optional[access_control.ACLToken] = None,
  ) -> ApiGetGrrVersionResult:
    del args, token  # Unused.

    version_dict = version.Version()

    result = ApiGetGrrVersionResult()
    result.major = version_dict["major"]
    result.minor = version_dict["minor"]
    result.revision = version_dict["revision"]
    result.release = version_dict["release"]
    return result


class ApiGetOpenApiDescriptionResult(rdf_structs.RDFProtoStruct):
  """An RDF wrapper for the OpenAPI description of the GRR API."""

  protobuf = metadata_pb2.ApiGetOpenApiDescriptionResult


class ApiGetOpenApiDescriptionHandler(api_call_handler_base.ApiCallHandler):
  """Renders a description of the API using the OpenAPI specification."""

  args_type = None
  result_type = ApiGetOpenApiDescriptionResult

  def __init__(self, router):
    self.router = router
    self.openapi_obj = None # The main OpenAPI description object.
    self.schema_objs = None

  def _SimplifyPathNode(self, node: str) -> str:
    if len(node) > 0 and node[0] == '<' and node[-1] == '>':
      node = node[1:-1]
      node = node.split(":")[-1]
      node = f"{{{node}}}"

    return node

  def _SimplifyPath(self, path: str) -> str:
    """Keep only fixed parts and parameter names from Werkzeug URL patterns.

    The OpenAPI specification requires that parameters are surrounded by { }
    which are added in _SimplifyPathNode.
    """

    nodes = path.split("/")
    simple_nodes = [self._SimplifyPathNode(node) for node in nodes]

    simple_path = '/'.join(simple_nodes)

    return simple_path

  def _GetPathArgsFromPath(self, path: str) -> [str]:
    """Extract path parameters from a Werkzeug Rule URL."""
    path_args = []

    nodes = path.split("/")
    for node in nodes:
      if len(node) > 0 and node[0] == '<' and node[-1] == '>':
        simple_node = self._SimplifyPathNode(node)
        simple_node = simple_node[1:-1]
        path_args.append(simple_node)

    return path_args

  def _GetTypeName(self, t):
    if inspect.isclass(t):
      return t.__name__

    return str(t) # Cover "BinaryStream" and None.

  def _SetMetadata(self):
    oas_version = "3.0.3"
    self.openapi_obj["openapi"] = oas_version

    # The Info Object "info" field.
    info_obj = dict()
    info_obj["title"] = "GRR Rapid Response API"
    info_obj["description"] = "GRR Rapid Response is an incident response " \
                              "framework focused on remote live forensics."

    contact_obj = dict()
    contact_obj["name"] = "GRR GitHub Repository"
    contact_obj["url"] = "https://github.com/google/grr"
    info_obj["contact"] = contact_obj

    license_obj = dict()
    license_obj["name"] = "Apache 2.0"
    license_obj["url"] = "http://www.apache.org/licenses/LICENSE-2.0"
    info_obj["license"] = license_obj

    version_dict = version.Version()
    info_obj["version"] = f"{version_dict['major']}.{version_dict['minor']}." \
                          f"{version_dict['revision']}." \
                          f"{version_dict['release']}"
    self.openapi_obj["info"] = info_obj

    self.openapi_obj["servers"] = []
    server_obj = dict()
    server_obj["url"] = "/"
    server_obj["description"] = "Root path of the GRR API"
    self.openapi_obj["servers"].append(server_obj)

  def _AddPrimitiveTypesSchemas(self):
    """Creates OpenAPI schemas for RDF primitives."""
    # TODO: Implement.
    pass

  def _ExtractSchema(self, t, visiting):
    if t is None:
      raise ValueError(f"Trying to extract schema for None type.")

    t_name = self._GetTypeName(t)
    if t_name in self.schema_objs:
      return self.schema_objs[t_name]

    if t_name in visiting:
      raise RuntimeError(
        f"Types definitions cycle detected: \"{t_name}\" is already on stack.")

    # Check if primitive type.
    # TODO: If primitive types schemas are added in _ExtractSchemasssssss, then they should be treated by the "if" above.

    schema_obj = dict()
    schema_obj["type"] = "object"
    schema_obj["properties"] = dict()
    visiting.add(t_name)

    # TODO: The following is semi-pseudocode. Make sure the members names are right.
    for type_info in t.type_infos():
      schema_obj["properties"][type_info.name] = self._ExtractSchema(type_info.type, visiting)

    visiting.remove(t_name)  # Not really useful, but for completeness.

    self.schema_objs[t_name] = schema_obj

    return schema_obj

  def _ExtractSchemas(self):
    # TODO 1: Traverse Router methods and extract a args_type_name/result_type_name -> Type dictionary = types
    # TODO 2: Traverse the types dictionary and for each value (type) declare its fields in an OpenAPI schema object, eventually by recursively declaring types of fields.

    # type_classes = dict()  # Class name -> Class.

    # router_methods = self.router.__class__.GetAnnotatedMethods()
    # for method_metadata in router_methods.values():
    #   args_type = method_metadata.args_type
    #   type_classes[self._GetTypeName(args_type)] = args_type
    #
    #   result_type = method_metadata.result_type
    #   type_classes[self._GetTypeName(result_type)] = result_type

    self.schema_objs = dict()  # Holds OpenAPI representations of types.
    visiting = set()  # Holds state of types extraction (white/gray nodes).
    self._AddPrimitiveTypesSchemas()


    router_methods = self.router.__class__.GetAnnotatedMethods()
    for method_metadata in router_methods.values():
      args_type = method_metadata.args_type
      args_type_name = self._GetTypeName(args_type)
      if args_type_name not in self.schema_objs:
        self._ExtractSchema(args_type, visiting)

      result_type = method_metadata.result_type
      result_type_name = self._GetTypeName(result_type)
      if result_type_name not in self.schema_objs:
        self._ExtractSchema(result_type, visiting)

  def _SetEndpoints(self):
    self._ExtractSchemas()
    # TODO: Set the path objects using $refs to the extracted schemas.

    pass

  def Handle(
      self,
      args: None,
      token: Optional[access_control.ACLToken] = None,
  ) -> ApiGetOpenApiDescriptionResult:
    result = ApiGetOpenApiDescriptionResult()

    if self.openapi_obj is not None:
      result.openapi_description = json.dumps(self.openapi_obj)
      return result

    self.openapi_obj = dict()
    self._SetMetadata()
    self._SetEndpoints()

    result.openapi_description = json.dumps(self.openapi_obj)
    return result

  def Handle_old(
      self,
      args: None,
      token: Optional[access_control.ACLToken] = None,
  ) -> ApiGetOpenApiDescriptionResult:

    result = ApiGetOpenApiDescriptionResult()

    oas_version = "3.0.3" #TODO: Don't hard code it.

    # The main OpenAPI description object.
    root_obj = dict()
    root_obj["openapi"] = oas_version

    # The Info Object "info" field.
    info_obj = dict()
    info_obj["title"] = "GRR Rapid Response API"
    info_obj["description"] = "GRR Rapid Response is an incident response " \
                              "framework focused on remote live forensics."

    contact_obj = dict()
    contact_obj["name"] = "GRR GitHub Repository"
    contact_obj["url"] = "https://github.com/google/grr"
    info_obj["contact"] = contact_obj

    license_obj = dict()
    license_obj["name"] = "Apache 2.0"
    license_obj["url"] = "http://www.apache.org/licenses/LICENSE-2.0"
    info_obj["license"] = license_obj

    version_dict = version.Version()
    info_obj["version"] = f"{version_dict['major']}.{version_dict['minor']}." \
                          f"{version_dict['revision']}." \
                          f"{version_dict['release']}"
    root_obj["info"] = info_obj

    # The Paths Object "paths" field.
    paths_obj = dict()

    router_methods = self.router.__class__.GetAnnotatedMethods()
    for router_method_name in router_methods:
      router_method = router_methods[router_method_name]
      for http_method, path, strip_root_types in router_method.http_methods:
        simple_path = self._SimplifyPath(path)
        path_args = self._GetPathArgsFromPath(path)
        path_args = set(path_args)

        if simple_path not in paths_obj:
          paths_obj[simple_path] = dict()

        # The Path Object associated with the current path.
        path_obj = paths_obj[simple_path]

        # The Operation Object associated with the current http method.
        operation_obj = dict()
        operation_obj["tags"] = [router_method.category, router_method_name]
        operation_obj["description"] = router_method.doc
        # TODO: Do we want a specific format for the operationId?
        operation_obj["operationId"] = \
          urlparse.quote(
            f"{http_method}-{path.replace('/', '-').replace('<', '_').replace('>', '_').replace(':', '-')}-{router_method.name}")
        operation_obj["parameters"] = []
        if router_method.args_type:
          type_infos = router_method.args_type().type_infos
        else:
          type_infos = []

        # TODO: Instead of defining parameter schemas here (and potentially
        # duplicating definitions, do it in two passes of the method arguments:
        # first define all the schemas in the "components" field of the OpenAPI
        # object (root) and then, in the second pass, just reference the
        # required types.
        body_parameters = []
        for type_info in type_infos:
          # The Parameter Object used to describe the parameter.
          parameter_obj = dict()
          parameter_obj["name"] = type_info.name
          if parameter_obj["name"] in path_args:
            # parameter_obj["name"] = f"<{type_info.name}>"
            parameter_obj["in"] = "path"
            parameter_obj["required"] = True
          elif http_method.upper() in ["GET", "HEAD"]:
            parameter_obj["in"] = "query"
          else:
            body_parameters.append(type_info)
            continue

          # The Schema Object used to describe the type of the parameter.
          schema_obj = dict()
          schema_obj["type"] = "string"
          parameter_obj["schema"] = schema_obj
          # TODO: Investigate more about style.
          parameter_obj["style"] = "simple"

          operation_obj["parameters"].append(parameter_obj)

        if body_parameters:
          # The Request Body Object which describes data sent in the message
          # body.
          request_body_obj = dict()
          request_body_obj["content"] = dict()
          # TODO: Not all requests sending a message body will use JSON.
          # They might use multipart/form-data and send a file?
          media_obj = dict()
          schema_obj = dict()
          schema_obj["type"] = "object"
          schema_obj["properties"] = dict()
          for type_info in body_parameters:
            schema_obj["properties"][type_info.name] = {"type": "string"} # TODO: Use proper types / ref.

          media_obj["schema"] = schema_obj
          request_body_obj["content"]["application/json"] = media_obj

          operation_obj["requestBody"] = request_body_obj

        # The Responses Object which describes the reponses associated with
        # HTTP response codes.
        responses_obj = dict()

        resp_success_obj = dict()
        if router_method.result_type \
            and router_method.result_type != "BinaryStream":
          type_infos = router_method.result_type().type_infos
          result_type_name = router_method.result_type.__name__
        else: # "BinaryStream" string or None.
          type_infos = []
          result_type_name = router_method.result_type

        resp_success_obj["description"] = \
          f"The call to the {router_method_name} API method returns " \
          f"successfully an object of type {result_type_name}."
        resp_success_obj["content"] = dict()

        media_obj = dict()
        schema_obj = dict()
        schema_obj["type"] = "object"
        schema_obj["properties"] = dict()

        for type_info in type_infos:
          schema_obj["properties"][type_info.name] = {"type": "string"} # TODO: Use proper types / ref.

        media_obj["schema"] = schema_obj

        if router_method.result_type == "BinaryStream":
          resp_success_obj["content"]["application/octet-stream"] = media_obj
        else:
          resp_success_obj["content"]["application/json"] = media_obj
        responses_obj["200"] = resp_success_obj

        resp_default_obj = dict()
        resp_default_obj["description"] = \
          f"The call to the {router_method_name} API method did not succeed."
        responses_obj["default"] = resp_default_obj

        operation_obj["responses"] = responses_obj

        path_obj[http_method.lower()] = operation_obj

    root_obj["paths"] = paths_obj

    result.openapi_description = json.dumps(root_obj)

    return result
