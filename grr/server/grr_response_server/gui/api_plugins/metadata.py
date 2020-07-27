#!/usr/bin/env python
# Lint as: python3
"""A module with API methods related to the GRR metadata."""
import json
import inspect

from urllib import parse as urlparse
from typing import Optional, Set

from google.protobuf.descriptor import Descriptor
from google.protobuf.descriptor import EnumDescriptor
from google.protobuf.descriptor import FieldDescriptor

from grr_response_core import version
from grr_response_core.lib.rdfvalues import structs as rdf_structs
from grr_response_core.lib.rdfvalues import proto2 as protobuf2
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

    self.proto_primitive_types_names = {
      protobuf2.TYPE_DOUBLE: "protobuf2.TYPE_DOUBLE",
      protobuf2.TYPE_FLOAT: "protobuf2.TYPE_FLOAT",
      protobuf2.TYPE_INT64: "protobuf2.TYPE_INT64",
      protobuf2.TYPE_UINT64: "protobuf2.TYPE_UINT64",
      protobuf2.TYPE_INT32: "protobuf2.TYPE_INT32",
      protobuf2.TYPE_FIXED64: "protobuf2.TYPE_FIXED64",
      protobuf2.TYPE_FIXED32: "protobuf2.TYPE_FIXED32",
      protobuf2.TYPE_BOOL: "protobuf2.TYPE_BOOL",
      protobuf2.TYPE_STRING: "protobuf2.TYPE_STRING",
      protobuf2.TYPE_BYTES: "protobuf2.TYPE_BYTES",
      protobuf2.TYPE_UINT32: "protobuf2.TYPE_UINT32",
      protobuf2.TYPE_SFIXED32: "protobuf2.TYPE_SFIXED32",
      protobuf2.TYPE_SFIXED64: "protobuf2.TYPE_SFIXED64",
      protobuf2.TYPE_SINT32: "protobuf2.TYPE_SINT32",
      protobuf2.TYPE_SINT64: "protobuf2.TYPE_SINT64",
    }
    self.primitive_types_names = \
      list(self.proto_primitive_types_names.values()) \
      + ["BinaryStream",]

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
    if isinstance(t, FieldDescriptor):
      if t.message_type:
        return self._GetTypeName(t.message_type)
      if t.enum_type:
        return self._GetTypeName(t.enum_type)

      return self._GetTypeName(t.type)

    if isinstance(t, Descriptor):
      return t.full_name

    if isinstance(t, EnumDescriptor):
      return t.full_name

    if inspect.isclass(t):
      return t.__name__

    if isinstance(t, int): # It's a protobuf.Descriptor.type value.
      return self.proto_primitive_types_names[t]

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
    """Creates OpenAPI schemas for Protobuf primitives and BinaryStream."""
    int_to_name = self.proto_primitive_types_names

    # protobuf2.TYPE_DOUBLE == 1
    schema_obj = dict()
    schema_obj["type"] = "number"
    schema_obj["format"] = "double"
    self.schema_objs[int_to_name[protobuf2.TYPE_DOUBLE]] = schema_obj

    # protobuf2.TYPE_FLOAT == 2
    schema_obj = dict()
    schema_obj["type"] = "number"
    schema_obj["format"] = "float"
    self.schema_objs[int_to_name[protobuf2.TYPE_FLOAT]] = schema_obj

    # protobuf2.TYPE_INT64 == 3
    schema_obj = dict()
    schema_obj["type"] = "integer"
    schema_obj["format"] = "int64"
    self.schema_objs[int_to_name[protobuf2.TYPE_INT64]] = schema_obj

    # protobuf2.TYPE_UINT64 == 4
    schema_obj = dict()
    schema_obj["type"] = "integer"
    schema_obj["format"] = "uint64"  # Undefined by OAS.
    self.schema_objs[int_to_name[protobuf2.TYPE_UINT64]] = schema_obj

    # protobuf2.TYPE_INT32 == 5
    schema_obj = dict()
    schema_obj["type"] = "integer"
    schema_obj["format"] = "int32"
    self.schema_objs[int_to_name[protobuf2.TYPE_INT32]] = schema_obj

    # protobuf2.TYPE_FIXED64 == 6
    schema_obj = dict()
    schema_obj["type"] = "integer"
    schema_obj["format"] = "uint64"
    self.schema_objs[int_to_name[protobuf2.TYPE_FIXED64]] = schema_obj

    # protobuf2.TYPE_FIXED32 == 7
    schema_obj = dict()
    schema_obj["type"] = "integer"
    schema_obj["format"] = "uint32"
    self.schema_objs[int_to_name[protobuf2.TYPE_FIXED32]] = schema_obj

    # protobuf2.TYPE_BOOL == 8
    schema_obj = dict()
    schema_obj["type"] = "boolean"
    self.schema_objs[int_to_name[protobuf2.TYPE_BOOL]] = schema_obj

    # protobuf2.TYPE_STRING == 9
    schema_obj = dict()
    schema_obj["type"] = "string"
    self.schema_objs[int_to_name[protobuf2.TYPE_STRING]] = schema_obj

    # protobuf2.TYPE_BYTES == 12
    schema_obj = dict()
    schema_obj["type"] = "string"
    schema_obj["format"] = "binary" # TODO: Here "byte" (base64) might be used.
    self.schema_objs[int_to_name[protobuf2.TYPE_BYTES]] = schema_obj

    # protobuf2.TYPE_UINT32 == 13
    schema_obj = dict()
    schema_obj["type"] = "integer"
    schema_obj["format"] = "uint32"
    self.schema_objs[int_to_name[protobuf2.TYPE_UINT32]] = schema_obj

    # protobuf2.TYPE_SFIXED32 == 15
    schema_obj = dict()
    schema_obj["type"] = "integer"
    schema_obj["format"] = "int32"
    self.schema_objs[int_to_name[protobuf2.TYPE_SFIXED32]] = schema_obj

    # protobuf2.TYPE_SFIXED64 == 16
    schema_obj = dict()
    schema_obj["type"] = "integer"
    schema_obj["format"] = "int64"
    self.schema_objs[int_to_name[protobuf2.TYPE_SFIXED64]] = schema_obj

    # protobuf2.TYPE_SINT32 == 17
    schema_obj = dict()
    schema_obj["type"] = "integer"
    schema_obj["format"] = "int32"
    self.schema_objs[int_to_name[protobuf2.TYPE_SINT32]] = schema_obj

    # protobuf2.TYPE_SINT64 == 18
    schema_obj = dict()
    schema_obj["type"] = "integer"
    schema_obj["format"] = "int64"
    self.schema_objs[int_to_name[protobuf2.TYPE_SINT64]] = schema_obj

    # BinaryStream
    schema_obj = dict()
    schema_obj["type"] = "string"
    schema_obj["format"] = "binary"
    self.schema_objs["BinaryStream"] = schema_obj

  def _ExtractEnumSchema(self, t: EnumDescriptor, visiting: Set[str]):
    """Extracts OpenAPI schema of a protobuf enum.

    This method should generally not be called directly, but rather through
    _ExtractSchema which takes care of error-verifications and caching.
    """
    t_name = self._GetTypeName(t)

    enum_schema_obj = dict()
    enum_schema_obj["type"] = "integer"
    enum_schema_obj["format"] = "int32"
    if len(t.values) > 0:
      enum_schema_obj["enum"] = [enum_value.number for enum_value in t.values]
      enum_schema_obj["description"] = \
        "\n".join([f"{enum_value.number} == {enum_value.name}"
                   for enum_value in t.values])
    else:
      enum_schema_obj["enum"] = []

    self.schema_objs[t_name] = enum_schema_obj

  def _ExtractMessageSchema(self, t: Descriptor, visiting: Set[str]):
    """Extracts OpenAPI schema of a protobuf message.

    This method should generally not be called directly, but rather through
    _ExtractSchema which takes care of error-verifications and caching.
    """
    t_name = self._GetTypeName(t)

    schema_obj = dict()
    schema_obj["type"] = "object"
    schema_obj["properties"] = dict()
    visiting.add(t_name)

    for field_descriptor in t.fields:
      field_name = field_descriptor.name
      message_descriptor = field_descriptor.message_type # None if not Message.
      enum_descriptor = field_descriptor.enum_type # None if not Enum.
      descriptor = message_descriptor or enum_descriptor

      if descriptor:
        self._ExtractSchema(descriptor, visiting)

      schema_or_ref_obj = \
        self._GetSchemaOrReferenceObject(self._GetTypeName(field_descriptor))
      if field_descriptor.label == protobuf2.LABEL_REPEATED:
        schema_obj["properties"][field_name] = {
          "type": "array",
          "items": schema_or_ref_obj,
        }
      else:
        schema_obj["properties"][field_name] = schema_or_ref_obj

    visiting.remove(t_name)
    self.schema_objs[t_name] = schema_obj

    return schema_obj

  def _ExtractSchema(self, t, visiting: Set[str]):
    if t is None:
      raise ValueError(f"Trying to extract schema of None.")

    t_name = self._GetTypeName(t)
    # "Primitive" types should be already present in self.schema_objs.
    if t_name in self.schema_objs:
      return self.schema_objs[t_name]

    if t_name in visiting:
      # Dependency cycle.
      return

    if isinstance(t, Descriptor):
      return self._ExtractMessageSchema(t, visiting)

    if isinstance(t, EnumDescriptor):
      return self._ExtractEnumSchema(t, visiting)

    raise TypeError(f"Don't know how to handle type \"{t_name}\" "
                    f"which is not a protobuf message Descriptor, "
                    f"nor an EnumDescriptor, nor a primitive type.")

  def _ExtractSchemas(self):
    """Extracts OpenAPI schemas for all the used protobuf types."""

    self.schema_objs = dict()  # Holds OpenAPI representations of types.
    self._AddPrimitiveTypesSchemas()

    visiting = set()  # Holds state of types extraction (white/gray nodes).
    router_methods = self.router.__class__.GetAnnotatedMethods()
    for method_metadata in router_methods.values():
      args_type = method_metadata.args_type
      if args_type:
        if inspect.isclass(args_type) \
            and issubclass(args_type, rdf_structs.RDFProtoStruct):
          self._ExtractSchema(args_type.protobuf.DESCRIPTOR, visiting)
        else:
          self._ExtractSchema(args_type, visiting)

      result_type = method_metadata.result_type
      if result_type:
        if inspect.isclass(result_type) \
            and issubclass(result_type, rdf_structs.RDFProtoStruct):
          self._ExtractSchema(result_type.protobuf.DESCRIPTOR, visiting)
        else:
          self._ExtractSchema(result_type, visiting)

  def _SetComponents(self):
    if self.schema_objs is None:
      raise ValueError("Called _SetComponents before extracting schemas.")

    # The Components Object "components" of the root OpenAPI object.
    components_obj = dict()
    schemas_obj = dict()

    type_names = set(self.schema_objs.keys())
    primitive_types_names = set(self.primitive_types_names)
    # Create components only for composite types.
    for type_name in type_names - primitive_types_names:
      schemas_obj[type_name] = self.schema_objs[type_name]

    components_obj["schemas"] = schemas_obj

    self.openapi_obj["components"] = components_obj

  def _GetSchemaOrReferenceObject(self, type_name: str):
    """Returns a Schema Object if primitive type, else a Reference Object.

    Primitive, not composite types don't have an actual schema, but rather an
    equivalent OpenAPI representation that gets returned for them.
    More complex types are expected to have been previously defined as OpenAPI
    components and are used through OpenAPI references.
    """
    if self.schema_objs is None:
      raise ValueError("Called _GetSchemaOrReferenceObject before extracting "
                       "schemas.")

    if type_name in self.primitive_types_names:
      schema_obj = self.schema_objs[type_name]
      return schema_obj

    reference_obj = dict()
    reference_obj["$ref"] = f"#/components/schemas/{type_name}"
    return reference_obj

  def _SetEndpoints(self):
    # The Paths Object "paths" field of the root OpenAPI object.
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
        operation_obj["tags"] = [router_method.category or "NoCategory",]
        operation_obj["description"] = router_method.doc or "No description."
        url_path = path.\
          replace('/', '-').\
          replace('<', '_').\
          replace('>', '_').\
          replace(':', '-')
        operation_obj["operationId"] = \
          urlparse.quote(f"{http_method}-{url_path}-{router_method.name}")

        # Parameters extraction.
        operation_obj["parameters"] = []
        field_descriptors = []
        if router_method.args_type:
          if not (
              inspect.isclass(router_method.args_type) and
              issubclass(router_method.args_type, rdf_structs.RDFProtoStruct)
          ):
            raise TypeError("Router method args type is not a RDFProtoStruct "
                            "subclass.")
          field_descriptors = router_method.args_type.protobuf.DESCRIPTOR.fields

        body_parameters = []
        for field_d in field_descriptors:
          # The Parameter Object used to describe the current parameter.
          parameter_obj = dict()
          parameter_obj["name"] = field_d.name
          if parameter_obj["name"] in path_args:
            parameter_obj["in"] = "path"
            parameter_obj["required"] = True
          elif http_method.upper() in ["GET", "HEAD"]:
            parameter_obj["in"] = "query"
          else:
            # This parameter will be added to the Request Body Object.
            body_parameters.append(field_d)
            continue

          field_type_name = self._GetTypeName(field_d)
          schema_or_ref_obj = self._GetSchemaOrReferenceObject(field_type_name)
          parameter_obj["schema"] = schema_or_ref_obj

          operation_obj["parameters"].append(parameter_obj)

        if body_parameters:
          # The Request Body Object which describes data sent in the message
          # body.
          request_body_obj = dict()
          request_body_obj["content"] = dict()
          media_obj = dict()
          schema_obj = dict()
          schema_obj["type"] = "object"
          schema_obj["properties"] = dict()
          for field_d in body_parameters:
            field_name = field_d.name
            field_type_name = self._GetTypeName(field_d)
            schema_or_ref_obj = \
              self._GetSchemaOrReferenceObject(field_type_name)
            schema_obj["properties"][field_name] = schema_or_ref_obj

          media_obj["schema"] = schema_obj
          request_body_obj["content"]["application/json"] = media_obj

          operation_obj["requestBody"] = request_body_obj

        # The Responses Object which describes the responses associated with
        # HTTP response codes.
        responses_obj = dict()

        # Building the Response Object for the 200 HTTP code.
        resp_success_obj = dict()
        if router_method.result_type:
          if inspect.isclass(router_method.result_type) and \
              issubclass(router_method.result_type, rdf_structs.RDFProtoStruct):
            result_type_name = \
              self._GetTypeName(router_method.result_type.protobuf.DESCRIPTOR)
          else:
            result_type_name = self._GetTypeName(router_method.result_type)

          resp_success_obj["description"] \
            = f"The call to the {router_method_name} API method succeeded " \
              f"and it returned an instance of {result_type_name}."

          media_obj = dict()
          schema_or_ref_obj = self._GetSchemaOrReferenceObject(result_type_name)
          media_obj["schema"] = schema_or_ref_obj

          resp_success_obj["content"] = dict()
          if router_method.result_type == "BinaryStream":
            resp_success_obj["content"]["application/octet-stream"] = media_obj
          else:
            resp_success_obj["content"]["application/json"] = media_obj
        else:
          resp_success_obj["description"] \
            = f"The call to the {router_method_name} API method succeeded."
        responses_obj["200"] = resp_success_obj

        resp_default_obj = dict()
        resp_default_obj["description"] = \
          f"The call to the {router_method_name} API method did not succeed."
        responses_obj["default"] = resp_default_obj

        operation_obj["responses"] = responses_obj

        path_obj[http_method.lower()] = operation_obj

    self.openapi_obj["paths"] = paths_obj
    print(f"primitive_types_names={self.primitive_types_names}")


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
    self._ExtractSchemas()
    self._SetComponents()
    self._SetEndpoints()

    result.openapi_description = json.dumps(self.openapi_obj)
    return result
