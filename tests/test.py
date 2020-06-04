from unittest.mock import Mock, patch

import pytest
from google.cloud.firestore_v1 import DocumentSnapshot
from pyrodantic.document import Document, FirestoreID, uuid4_hex


DOC_ID = 'doc-id'
HEX = 'ab12cd'


class MockUUID:
    hex = HEX


def mock_data(with_id=False):
    data = {'str_attr': 'foo', 'int_attr': 1}
    if with_id is not False:
        id = DOC_ID if with_id is True else with_id
        data['doc_id'] = id
    return data


def mock_snapshot(exists=True):
    reference = Mock(id=DOC_ID)
    return DocumentSnapshot(reference, mock_data(), exists, None, None, None)


def snapshot_generator(snapshots=None):
    if snapshots is None:
        snapshots = [mock_snapshot()]
    for i in snapshots:
        yield i


def test_uuid4_hex():
    with patch('pyrodantic.document.uuid4') as mock:
        mock.return_value = MockUUID()
        assert uuid4_hex() == HEX


class Document1(Document):
    doc_id: FirestoreID = None
    str_attr: str
    int_attr: int

    class Firestore:
        collection = 'test-collection'


def make_doc(with_id=False, client=None):
    client = client or Mock()
    return Document1(client, **mock_data(with_id=with_id))


def test_document_class_no_id_attr():
    with pytest.raises(TypeError):
        class BadDocument(Document):
            foo: str


def test_collection():
    client = object()
    ref = Document1.collection_ref(client)
    assert ref._path == ('test-collection',)
    assert ref._client == client


def test_document_init():
    client = object()
    doc = Document1(client, **mock_data())
    assert doc.__firestore__.client == client
    assert doc.dict() == mock_data(with_id=None)


def test_document_from_snapshot():
    client = object()
    reference = Mock(id=DOC_ID)
    snapshot = DocumentSnapshot(reference, mock_data(), True, None, None, None)
    doc = Document1._from_firestore_snapshot(snapshot, firestore_client=client)
    assert doc.__firestore__.client == client
    assert doc.dict() == mock_data(with_id=True)


def test_document_get():
    with patch('pyrodantic.document.DocumentReference') as MockDocRef:
        reference = Mock(id='doc-id')
        data = {'str_attr': 'foo', 'int_attr': 1}
        mock_doc = Mock()
        mock_doc.get.return_value = DocumentSnapshot(reference, data, True, None, None, None)
        MockDocRef.return_value = mock_doc
        doc = Document1.get('doc-id', firestore_client=None)
        data['doc_id'] = 'doc-id'
        assert doc.dict() == data


def test_document_where():
    with patch(f'{__name__}.Document1.collection_ref') as mock_collection_ref:
        stream = Mock()
        stream.stream.return_value = snapshot_generator()
        ref = Mock()
        ref.where.return_value = stream
        mock_collection_ref.return_value = ref
        docs = list(Document1.where('str_attr', '==', 'foo', None).stream())
        assert len(docs) == 1
        doc = docs.pop()
        assert doc.dict() == mock_data(with_id=True)


@pytest.mark.parametrize('data,create,expected',
                         [(mock_data(), False, None),
                          (mock_data(), True, HEX),
                          (mock_data(with_id=True), False, DOC_ID),
                          (mock_data(with_id=True), True, DOC_ID)])
def test_document_id(data, create, expected):
    with patch(f'{__name__}.Document1.__firestore__.id_generator', lambda: HEX):
        doc = Document1(None, **data)
        assert doc._document_id(create=create) == expected


def test_document_create():
    mock_ref = Mock()
    with patch(f'{__name__}.Document1.__firestore__.id_generator', lambda: HEX):
        with patch('pyrodantic.document.DocumentReference', Mock(return_value=mock_ref)):
            doc = make_doc()
            doc.create()
    mock_ref.create.assert_called_with(mock_data())
    assert doc.doc_id == HEX


def test_document_update():
    mock_ref = Mock()
    with patch('pyrodantic.document.DocumentReference', Mock(return_value=mock_ref)):
        doc = make_doc()
        doc.str_attr = 'bar'
        doc.update()
    expected = mock_data()
    expected['str_attr'] = 'bar'
    mock_ref.update.assert_called_with(expected)


def test_document_delete():
    mock_ref = Mock()
    with patch('pyrodantic.document.DocumentReference', Mock(return_value=mock_ref)):
        doc = make_doc(with_id=True)
        doc.delete()
    mock_ref.delete.assert_called_once()


def test_document_delete_unsaved():
    mock_ref = Mock()
    with patch('pyrodantic.document.DocumentReference', Mock(return_value=mock_ref)):
        doc = make_doc(with_id=False)
        doc.delete()
    assert not mock_ref.delete.called
