# Pyrodantic

[Pydantic](https://pydantic-docs.helpmanual.io/) models for [Google Firestore](https://cloud.google.com/firestore).

Inspired by [fireclass](https://github.com/nabla-c0d3/fireclass).

## Installation
pip install pyrodantic

## Usage

```python
from google.cloud.firestore import Client
from pyrodantic.document import Document, FirestoreID


firestore_client = Client()


class TestDocument(Document):
    document_id: FirestoreID = None
    test_string: str
    test_int: int
    test_default: str = 'default'
    class Firestore:
        collection = 'test-collection'


doc = TestDocument(firestore_client, test_string='foo', test_int=1)
# TestDocument(document_id=None, test_string='foo', test_int=1, test_default='default')

doc.create()
# TestDocument(document_id='4f7be295accc473aa87844ec6f98443c', test_string='foo', test_int=1, test_default='default')

doc = TestDocument.get('4f7be295accc473aa87844ec6f98443c', firestore_client=firestore_client)
# TestDocument(document_id='4f7be295accc473aa87844ec6f98443c', test_string='foo', test_int=1, test_default='default')

doc.delete()

doc = TestDocument.get('4f7be295accc473aa87844ec6f98443c', firestore_client=firestore_client)
# doc == None
```

## TODO

* Queries (`.where(...)`)
