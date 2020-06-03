from uuid import uuid4

from pydantic import BaseModel
from pydantic.main import ModelMetaclass
from google.cloud.firestore import Client as FirestoreClient
from google.cloud.firestore_v1.document import DocumentReference


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
    return type('FirestoreConfig', base_classes, {})


class FirestoreID(str):
    pass


class FirestoreConfig:
    collection = None
    id_generator = uuid4_hex


_is_document_class_defined = False


class DocumentMeta(ModelMetaclass):
    def __new__(cls, name, bases, namespace, **kwargs):
        firestore = FirestoreConfig
        for base in reversed(bases):
            if _is_document_class_defined and issubclass(base, Document) and base != Document:
                firestore = inherit_config(base.__firestore__, firestore)
        firestore = inherit_config(namespace.get('Firestore'), firestore)
        annotations = namespace.get('__annotations__', {})

        ids = {k: v for k, v in annotations.items() if issubclass(v, FirestoreID)}

        if _is_document_class_defined and len(ids) != 1 and not hasattr(firestore, 'id_attr'):
            raise TypeError(f'"{name}" must have exactly one attribute of type '
                            'FirestoreID (or subclass thereof).')
        elif len(ids) == 1:
            id_attr = list(ids.keys())[0]
            setattr(firestore, 'id_attr', id_attr)
        namespace['__firestore__'] = firestore
        cls = ModelMetaclass.__new__(cls, name, bases, namespace, **kwargs)
        return cls


class Document(BaseModel, metaclass=DocumentMeta):
    Firestore = FirestoreConfig

    def __init__(self, firestore_client, **kwargs):
        self.__firestore__.client = firestore_client
        BaseModel.__init__(self, **kwargs)

    @classmethod
    def get(cls, document_id: str, *, firestore_client: FirestoreClient):
        path = [cls.__firestore__.collection, document_id]

        doc = DocumentReference(*path, client=firestore_client).get()
        if not doc.exists:
            return None
        else:
            data = doc.to_dict()
            data[cls.__firestore__.id_attr] = document_id
            return cls(firestore_client, **data)

    def _document_id(self, create=False):
        id_ = getattr(self, self.__firestore__.id_attr)
        if id_ is None and create:
            if not callable(self.__firestore__.id_generator):
                TypeError('No id generator available for "self.__class__"}')
            id_ = self.__firestore__.id_generator()
            setattr(self, self.__firestore__.id_attr, id_)
        return id_

    def doc_ref(self, create=False):
        id_ = self._document_id(create=create)
        path = [self.__firestore__.collection, id_]
        return DocumentReference(*path, client=self.__firestore__.client)

    def create(self):
        data = self.dict()
        data.pop(self.__firestore__.id_attr)
        ref = self.doc_ref(create=True)
        ref.create(data)

    def update(self):
        ref = self.doc_ref()
        data = self.dict()
        data.pop(self.__firestore__.id_attr)
        ref.update(data)

    def delete(self):
        if not self._document_id():
            return
        self.doc_ref().delete()


_is_document_class_defined = True
