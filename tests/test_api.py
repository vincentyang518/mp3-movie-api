import sqlite3
import subprocess
import sys
from io import BytesIO
import pandas as pd
import pytest
import main
from src import MovieStorage
from src.database import get_connection
from src.storage import MOVIE_COLUMNS


def upload(client, content, name='sample_movies.csv'):
    return client.post('/upload', files={'file': (name, content, 'text/csv')})


def test_empty(client):
    assert client.get('/movies').json() == {'data': [], 'total_rows': 0}
    assert client.get('/movies/search').json() == []
    assert client.post('/movies/process', json={}).status_code == 400
    assert list(main.storage.get().columns) == MOVIE_COLUMNS


def test_assignment_examples(client, sample):
    assert upload(client, sample).json() == {'filename':'sample_movies.csv', 'rows':20, 'columns':4, 'column_names':MOVIE_COLUMNS}
    assert client.get('/movies?limit=2').json() == {'data':[
        {'id':1,'title':'Movie A','release_year':2020,'rating':8.0,'genre':'Drama'},
        {'id':2,'title':'Movie B','release_year':2021,'rating':8.5,'genre':'Comedy'}], 'total_rows':20}
    assert client.get('/movies/search?min_rating=8.5&limit=2').json() == [{'id':4,'title':'Movie C'},{'id':2,'title':'Movie B'}]
    assert client.get('/movies/search?columns=title&columns=rating&min_rating=8.5&limit=2').json() == [
        {'id':4,'title':'Movie C','rating':9.0},{'id':2,'title':'Movie B','rating':8.5}]
    assert client.get('/movies/search?min_rating=10').json() == []
    upload(client, sample)
    assert client.get('/movies').json()['total_rows'] == 20
    assert client.get('/movies?limit=1').json()['data'][0]['id'] == 1


@pytest.mark.parametrize('content,name', [
    (b'x','bad.txt'), (b'','empty.csv'),
    (b'title,release_year,rating,genre\n','header.csv'),
    (b'title,rating\nA,8\n','missing.csv'),
    (b'title,release_year,rating,genre,extra\nA,2020,8,Drama,1\n','extra.csv'),
    (b'title,release_year,rating,genre\n"unclosed','broken.csv'),
    (b'\xff\xfe','encoding.csv'),
    (b'title,title,rating,genre\nA,2020,8,Drama\n','duplicate.csv')])
def test_bad_upload_preserves_collection(client, sample, content, name):
    upload(client, sample)
    assert upload(client,content,name).status_code == 400
    assert client.get('/movies').json()['total_rows'] == 20
    response = client.get('/health')
    assert response.json() == {'status':'ok','version':'1.0.0'}
    assert response.headers['X-Request-ID']


@pytest.mark.parametrize('url,status', [('/movies?limit=0',422),('/movies/search?limit=0',422),
    ('/movies/search?min_rating=-1',422),('/movies/search?min_rating=11',422),
    ('/movies/search?columns=unknown',400),('/movies/search?columns=title%3BDROP%20TABLE%20movies',400),
    ('/movies/search?columns=',400)])
def test_query_errors(client,url,status):
    assert client.get(url).status_code == status
    assert client.get('/health').status_code == 200


def test_reordered_columns_and_null(client):
    response = upload(client,b'genre,rating,title,release_year\nDrama,,A,2020\n')
    assert response.status_code == 200
    assert response.json()['column_names'] == MOVIE_COLUMNS
    assert client.get('/movies').json()['data'][0]['rating'] is None
    assert client.get('/movies/search').json() == []


def test_process_reuses_mp2(client,sample):
    upload(client,sample)
    response = client.post('/movies/process',json={
        'validation':{'required_columns':MOVIE_COLUMNS,'numeric_columns':['rating','release_year']},
        'processing':{'remove_duplicates':True,'missing':{'enabled':True,'axis':'rows'},
                      'outliers':{'enabled':True,'columns':['rating'],'method':'iqr','threshold':1.5}}})
    assert response.status_code == 200
    assert response.json() == {'validation_rows_removed':0,'cleaning_report':{
        'rows_before':20,'rows_after':16,'rows_removed':4,'columns_before':4,'columns_after':4,'columns_removed':0}}
    assert main.storage.count_movies() == 16


def test_validation_and_error(client):
    upload(client,b'title,release_year,rating,genre\nA,2020,wrong,Drama\nB,2021,8,Comedy\n')
    response = client.post('/movies/process',json={'validation':{'numeric_columns':['rating']}})
    assert response.json()['validation_rows_removed'] == 1
    assert main.storage.count_movies() == 1
    assert client.post('/movies/process',json={'processing':{'missing':{'axis':'bad'}}}).status_code == 400
    assert main.storage.count_movies() == 1


def test_processing_cannot_remove_columns(client):
    upload(client,b'title,release_year,rating,genre\nA,2020,,Drama\n')
    assert client.post('/movies/process',json={'processing':{'missing':{'axis':'columns'}}}).status_code == 400
    assert main.storage.count_movies() == 1


def test_persistence_in_fresh_process(tmp_path,sample):
    path = tmp_path/'nested/movies.db'
    MovieStorage(path).save(pd.read_csv(BytesIO(sample)))
    code = 'from src import MovieStorage; import sys; s=MovieStorage(sys.argv[1]); assert s.count_movies()==20; assert s.query_movies(["title"],8.5,2)==[{"id":4,"title":"Movie C"},{"id":2,"title":"Movie B"}]'
    subprocess.run([sys.executable,'-c',code,str(path)],check=True)


def test_atomic_rollback(tmp_path):
    store = MovieStorage(tmp_path/'movies.db')
    store.save(pd.DataFrame([['Original',2020,8,'Drama']],columns=MOVIE_COLUMNS))
    connection = get_connection(store.db_path)
    try:
        connection.execute("CREATE TRIGGER reject_bad BEFORE INSERT ON movies WHEN NEW.title='Bad' BEGIN SELECT RAISE(ABORT, 'bad title'); END")
        connection.commit()
    finally:
        connection.close()
    with pytest.raises(sqlite3.IntegrityError):
        store.save(pd.DataFrame([['Good',2021,9,'Drama'],['Bad',2022,7,'Comedy']],columns=MOVIE_COLUMNS))
    assert store.count_movies() == 1
    assert store.get()['title'].tolist() == ['Original']


def test_storage_nulls_and_columns(tmp_path):
    store = MovieStorage(tmp_path/'movies.db')
    store.save(pd.DataFrame([[None,None,float('nan'),None]],columns=MOVIE_COLUMNS))
    assert store.select_columns(MOVIE_COLUMNS) == [dict(id=1,title=None,release_year=None,rating=None,genre=None)]
    for columns in ([],['nope'],['title; DROP TABLE movies']):
        with pytest.raises(ValueError): store.select_columns(columns)
        with pytest.raises(ValueError): store.query_movies(columns,0,5)
    store.save(pd.DataFrame(columns=MOVIE_COLUMNS))
    assert store.count_movies() == 0
    assert list(store.get().columns) == MOVIE_COLUMNS


def test_default_processing_keeps_mp2_behavior(client, sample):
    upload(client, sample)
    response = client.post('/movies/process', json={})
    assert response.status_code == 200
    assert response.json() == {
        'validation_rows_removed': 0,
        'cleaning_report': {'rows_before': 20, 'rows_after': 18, 'rows_removed': 2,
                            'columns_before': 4, 'columns_after': 4, 'columns_removed': 0},
    }
    assert client.get('/movies').json()['total_rows'] == 18


@pytest.mark.parametrize('config', [
    {'validation': {'required_columns': ['missing']}},
    {'validation': {'numeric_columns': ['missing']}},
    {'processing': {'outliers': {'enabled': True, 'columns': ['rating'], 'method': 'unsupported'}}},
])
def test_mp2_validation_errors_preserve_data(client, sample, config):
    upload(client, sample)
    before = client.get('/movies').json()
    assert client.post('/movies/process', json=config).status_code == 400
    assert client.get('/movies').json() == before


def test_schema_matches_assignment(tmp_path):
    path = tmp_path / 'nested/movies.db'
    MovieStorage(path)
    connection = get_connection(path)
    try:
        schema = [dict(row) for row in connection.execute('PRAGMA table_info(movies)')]
        assert [row['name'] for row in schema] == ['id'] + MOVIE_COLUMNS
        assert [row['type'] for row in schema] == ['INTEGER', 'TEXT', 'INTEGER', 'REAL', 'TEXT']
        assert schema[0]['pk'] == 1
        assert all(row['notnull'] == 0 for row in schema[1:])
    finally:
        connection.close()


def test_required_logs_and_openapi(client, sample, caplog):
    import logging
    caplog.set_level(logging.DEBUG)
    upload(client, sample)
    client.get('/movies/search?columns=title&columns=rating&min_rating=8.5&limit=2')
    assert any(record.levelno == logging.DEBUG and 'Stored movies in SQLite: rows=20' in record.message
               for record in caplog.records)
    assert any(record.levelno == logging.INFO and 'Uploaded movies: filename=sample_movies.csv, rows=20' in record.message
               for record in caplog.records)
    assert any(record.levelno == logging.INFO and "columns=['title', 'rating']" in record.message
               and 'returned_rows=2' in record.message for record in caplog.records)
    spec = client.get('/openapi.json').json()
    assert {'/health', '/upload', '/movies', '/movies/search', '/movies/process'} == set(spec['paths'])
    assert {'MovieUploadInfo', 'MovieDataResponse', 'MovieProcessingReport'} <= set(spec['components']['schemas'])


def test_movies_persist(client, test_storage, uploaded_movies):
    reopened = MovieStorage(test_storage.db_path)
    movies = reopened.get()
    assert reopened.count_movies() == len(movies) == 20
    assert list(movies.columns) == MOVIE_COLUMNS
    expected_titles = [
        'Movie A', 'Movie B', 'Movie B', 'Movie C', 'Movie D', 'Movie D',
        *[f'Movie {letter}' for letter in 'EFGHIJKLMNOPQR'],
    ]
    assert movies['title'].tolist() == expected_titles
    saved = reopened.select_columns(MOVIE_COLUMNS, limit=100)
    response = client.get('/movies?limit=100')
    assert response.status_code == 200
    assert response.json()['total_rows'] == 20
    assert response.json()['data'] == saved
    assert [row['id'] for row in saved] == list(range(1, 21))
    assert [row['id'] for row in response.json()['data']] == list(range(1, 21))


def test_cache_and_processing(client, uploaded_movies, processing_body):
    responses = {}
    for limit in (100, 1):
        response = client.get('/movies', params={'limit': limit})
        assert response.status_code == 200
        responses[limit] = response.json()
        assert response.json()['total_rows'] == 20
        assert len(response.json()['data']) == min(limit, 20)
        assert main.cache.get(limit) == response.json()
    repeat = client.get('/movies?limit=100')
    assert repeat.status_code == 200
    assert repeat.json() == responses[100]

    processed = client.post('/movies/process', json=processing_body)
    assert processed.status_code == 200
    assert processed.json() == {
        'validation_rows_removed': 0,
        'cleaning_report': {
            'rows_before': 20, 'rows_after': 16, 'rows_removed': 4,
            'columns_before': 4, 'columns_after': 4, 'columns_removed': 0,
        },
    }
    assert main.cache.get(100) is None
    assert main.cache.get(1) is None
    refreshed = client.get('/movies?limit=100')
    assert refreshed.status_code == 200
    body = refreshed.json()
    assert body['total_rows'] == len(body['data']) == 16
    assert [row['title'] for row in body['data']] == [f'Movie {letter}' for letter in 'ABCDEFGHIJKLMNOP']
    assert [row['id'] for row in body['data']] == list(range(1, 17))
    assert main.cache.get(100) == body


def test_cache_hit_skips_database(client, uploaded_movies, monkeypatch):
    first = client.get('/movies?limit=100')
    assert first.status_code == 200

    def fail_on_database_read(*args, **kwargs):
        pytest.fail('Cache hit must skip SQL retrieval and count')

    monkeypatch.setattr(main.storage, 'select_columns', fail_on_database_read)
    monkeypatch.setattr(main.storage, 'count_movies', fail_on_database_read)
    second = client.get('/movies?limit=100')
    assert second.status_code == 200
    assert second.json() == first.json()


def test_upload_invalidates_all_limits(client, uploaded_movies, sample_csv_bytes, processing_body):
    assert client.post('/movies/process', json=processing_body).status_code == 200
    for limit in (100, 1):
        assert client.get('/movies', params={'limit': limit}).json()['total_rows'] == 16
    assert upload(client, sample_csv_bytes).status_code == 200
    assert main.cache.get(100) is None
    assert main.cache.get(1) is None
    assert client.get('/movies').json()['total_rows'] == 20


def test_failed_writes_preserve_cache(client, uploaded_movies, monkeypatch, processing_body):
    before = client.get('/movies').json()
    assert upload(client, b'title,rating\nA,8\n').status_code == 400
    assert main.cache.get(100) == before
    invalid = {'validation': {'required_columns': ['unknown']}}
    assert client.post('/movies/process', json=invalid).status_code == 400
    assert main.cache.get(100) == before

    def fail_save(*args, **kwargs):
        raise sqlite3.OperationalError('simulated save failure')

    monkeypatch.setattr(main.storage, 'save', fail_save)
    for action in (
        lambda: upload(client, b'title,release_year,rating,genre\nNew,2020,8,Drama\n'),
        lambda: client.post('/movies/process', json=processing_body),
    ):
        assert action().status_code == 500
        assert main.cache.get(100) == before
        assert main.storage.count_movies() == 20


def test_search_is_uncached(client, uploaded_movies, monkeypatch):
    client.get('/movies')
    expected = [{'id': 4, 'title': 'Movie C'}]
    calls = []

    def query(*args):
        calls.append(args)
        return expected

    monkeypatch.setattr(main.storage, 'query_movies', query)
    for _ in range(2):
        response = client.get('/movies/search?min_rating=9')
        assert response.status_code == 200
        assert response.json() == expected
    assert len(calls) == 2


def test_empty_processed_collection_is_cached(client):
    upload(client, b'title,release_year,rating,genre\nA,2020,,Drama\n')
    assert client.get('/movies').json()['total_rows'] == 1
    assert client.post('/movies/process', json={}).status_code == 200
    assert main.cache.get(100) is None
    assert client.get('/movies').json() == {'data': [], 'total_rows': 0}
    assert main.cache.get(100) == {'data': [], 'total_rows': 0}


def test_cache_expiration_and_logs(caplog):
    import logging
    from unittest.mock import patch
    from src import MovieCache

    caplog.set_level(logging.DEBUG)
    cache = MovieCache()
    response = {'data': [], 'total_rows': 0}
    with patch('time.time', return_value=2_000_000_000):
        assert cache.get(100) is None
        cache.set(100, response)
        assert cache.client.ttl(cache.make_key(100)) == 90
        assert cache.get(100) == response
    with patch('time.time', return_value=2_000_000_091):
        assert cache.get(100) is None
    cache.invalidate()
    assert 'Cache MISS: movies:limit:100' in caplog.text
    assert 'Cache HIT: movies:limit:100' in caplog.text
    assert 'Invalidated movie cache' in caplog.text
