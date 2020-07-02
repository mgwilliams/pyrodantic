from typing import Any, Iterator, TypeVar
from uuid import uuid4

from pydantic import BaseModel
from pydantic.main import ModelMetaclass
from google.cloud.firestore import Client as FirestoreClient
from google.cloud.firestore_v1 import (
    CollectionReference,
    DocumentReference,
    DocumentSnapshot,
    Query as FirestoreQuery,
)
from typing_extensions import Literal


def uuid4_hex():
    return uuid4().hex


def inherit_config(self_config, parent_config):
    # copied from pydantic.main
    if not self_config:
        base_classes = (parent_config,)
    elif self_config == parent_config:
        base_classes = (self_config,)
    else:
        base_classes = self_config, parent_config  # type: ignore
    return type("FirestoreConfig", base_classes, {})


class FirestoreID(str):
    pass


class FirestoreConfig:
    collection = None
    id_generator: callable = uuid4_hex
    id_generator_args: tuple = None
    id_generator_kwargs: dict = None
    retry_create_on_conflict: bool = True


ComparisonOperator = Literal["<", "<=", "==", ">=", ">", "array_contains"]
_DocumentSubclassTypeVar = TypeVar("_DocumentSubclassTypeVar", bound="Document")

_is_document_class_defined = False


class DocumentMeta(ModelMetaclass):
    def __new__(cls, name, bases, namespace, **kwargs):
        firestore = FirestoreConfig
        for base in reversed(bases):
            if (
                _is_document_class_defined
                and issubclass(base, Document)
                and base != Document
            ):
                firestore = inherit_config(base.__firestore__, firestore)
        firestore = inherit_config(namespace.get("Firestore"), firestore)
        annotations = namespace.get("__annotations__", {})

        ids = {k: v for k, v in annotations.items() if issubclass(v, FirestoreID)}

        if (
            _is_document_class_defined
            and len(ids) != 1
            and not hasattr(firestore, "id_attr")
        ):
            raise TypeError(
                f'"{name}" must have exactly one attribute of type FirestoreID.'
            )
        elif len(ids) == 1:
            id_attr = list(ids.keys())[0]
            setattr(firestore, "id_attr", id_attr)
        namespace["__firestore__"] = firestore
        cls = ModelMetaclass.__new__(cls, name, bases, namespace, **kwargs)
        return cls


class Document(BaseModel, metaclass=DocumentMeta):
    Firestore = FirestoreConfig

    def __init__(self, firestore_client: FirestoreClient, **kwargs) -> None:
        self.__firestore__.client = firestore_client
        BaseModel.__init__(self, **kwargs)

    @classmethod
    def collection_ref(cls, firestore_client: FirestoreClient) -> CollectionReference:
        return CollectionReference(
            cls.__firestore__.collection, client=firestore_client
        )

    @classmethod
    def _from_firestore_snapshot(
        cls, snapshot: DocumentSnapshot, *, firestore_client: FirestoreClient
    ) -> _DocumentSubclassTypeVar:
        data = snapshot.to_dict()
        data[cls.__firestore__.id_attr] = snapshot.id
        return cls(firestore_client, **data)

    @classmethod
    def get(
        cls, document_id: str, *, firestore_client: FirestoreClient
    ) -> _DocumentSubclassTypeVar:
        path = [cls.__firestore__.collection, document_id]

        snapshot = DocumentReference(*path, client=firestore_client).get()
        if snapshot is None:
            return None
        else:
            return cls._from_firestore_snapshot(
                snapshot, firestore_client=firestore_client
            )

    @classmethod
    def where(
        cls,
        field: str,
        operator: ComparisonOperator,
        search: Any,
        firestore_client: FirestoreClient,
    ) -> "Query":
        collection = cls.collection_ref(firestore_client)
        query = collection.where(field, operator, search)
        return Query(cls, query, firestore_client)

    def _document_id(self, create: bool = False, new_id: bool = False) -> str:
        id_ = None if new_id else getattr(self, self.__firestore__.id_attr)
        if id_ is None and create:
            if not callable(self.__firestore__.id_generator):
                TypeError('No id generator available for "self.__class__"}')
            args = self.__firestore__.id_generator_args or tuple()
            kwargs = self.__firestore__.id_generator_kwargs or dict()
            id_ = self.__firestore__.id_generator(*args, **kwargs)
            setattr(self, self.__firestore__.id_attr, id_)
        return id_

    def doc_ref(self, create: bool = False, new_id: bool = False) -> DocumentReference:
        id_ = self._document_id(create=create, new_id=new_id)
        path = [self.__firestore__.collection, id_]
        return DocumentReference(*path, client=self.__firestore__.client)

    def create(self) -> None:
        data = self.dict()
        data.pop(self.__firestore__.id_attr)
        new_id = False
        while True:
            try:
                ref = self.doc_ref(create=True, new_id=new_id)
                ref.create(data)
            except Conflict:
                if self.__firestore__.retry_create_on_conflict:
                    new_id = True
                    continue
                else:
                    raise

    def update(self) -> None:
        ref = self.doc_ref()
        data = self.dict()
        data.pop(self.__firestore__.id_attr)
        ref.update(data)

    def delete(self) -> None:
        if not self._document_id():
            return
        self.doc_ref().delete()


_is_document_class_defined = True


class Query:
    def __init__(
        self,
        document_cls: Document,
        firestore_query: FirestoreQuery,
        firestore_client: FirestoreClient,
    ) -> None:
        self._document_cls = document_cls
        self._firestore_query = firestore_query
        self._firestore_client = firestore_client

    def limit(self, count: int) -> "Query":
        new_query = self._firestore_query.limit(count)
        return Query(self._document_cls, new_query, self._firestore_client)

    def stream(self) -> Iterator["Query"]:
        for snapshot in self._firestore_query.stream():
            yield self._document_cls._from_firestore_snapshot(
                snapshot, firestore_client=self._firestore_client
            )

    def where(
        self, field_path: str, op_string: ComparisonOperator, value: Any
    ) -> "Query":
        return Query(
            self._document_cls,
            self._firestore_query.where(field_path, op_string, value),
            self._firestore_client,
        )
