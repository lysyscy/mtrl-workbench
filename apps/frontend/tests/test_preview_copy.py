"""Only synthetic schemas: copy consistency, credential stripping and external route denial."""
import os
from pathlib import Path
import pytest
from sqlalchemy import create_engine, text
from tools.dev.frontend_preview import isolated_database
from tools.dev.frontend_preview_copy import copy_snapshot, clone_from_source, restrict_copy_preview


def test_copy_snapshot_preserves_business_and_sequences_without_credentials():
    source_path=Path(os.environ['MTRL_PREVIEW_SOURCE_ENV'])
    with isolated_database(source_path) as src_env, isolated_database(source_path) as dst_env:
        src_schema=src_env['PGOPTIONS'].split('search_path=',1)[1];dst_schema=dst_env['PGOPTIONS'].split('search_path=',1)[1]
        se=create_engine(src_env['DATABASE_URL'],connect_args={'options':src_env['PGOPTIONS']},isolation_level='REPEATABLE READ',hide_parameters=True)
        de=create_engine(dst_env['DATABASE_URL'],connect_args={'options':dst_env['PGOPTIONS']},hide_parameters=True)
        try:
            with se.begin() as source:
                source.execute(text("UPDATE user_account SET password='synthetic-secret',i8_user='synthetic-login',i8_password='synthetic-secret'"))
                source.execute(text("INSERT INTO app_setting(key,value,updated_at) VALUES ('i8_base_url','https://synthetic.invalid',now())"))
            with se.connect() as source, source.begin(), de.begin() as target:
                source.exec_driver_sql('SET TRANSACTION READ ONLY')
                receipt=copy_snapshot(source,target,src_schema,dst_schema)
                assert receipt['ledger_projects_verified']==3
                assert receipt['tables']['opening_balance']['rows']==4
                assert target.exec_driver_sql("SELECT count(*) FROM user_account WHERE password<>'' OR i8_user<>'' OR i8_password<>''").scalar_one()==0
                assert target.exec_driver_sql("SELECT count(*) FROM user_account WHERE status<>'已停用'").scalar_one()==0
                assert target.exec_driver_sql('SELECT count(*) FROM app_setting').scalar_one()==0
                assert source.exec_driver_sql("SELECT count(*) FROM user_account WHERE password='synthetic-secret'").scalar_one()==2
                before=target.exec_driver_sql('SELECT max(id) FROM user_account').scalar_one()
                from app.mod15_user.models import UserAccount
                created=target.execute(UserAccount.__table__.insert().values(account='copy-test-local',name='合成新增身份',password='').returning(UserAccount.id)).scalar_one()
                assert created>before
        finally:
            se.dispose();de.dispose()


def test_copy_rejects_same_database_before_connecting():
    with pytest.raises(RuntimeError,match='separate local'):
        clone_from_source('postgresql://unused@localhost/same','postgresql://unused@localhost/same','preview_test')


def test_copy_preview_blocks_external_and_unrelated_writes():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    app=FastAPI();calls=[]
    @app.api_route('/api/m02/fetch',methods=['GET','POST'])
    def external():calls.append('external');return {'ok':True}
    @app.post('/api/m05/history/save')
    def save():calls.append('local');return {'ok':True}
    restrict_copy_preview(app)
    with TestClient(app) as client:
        for method,path in [('POST','/api/m02/fetch'),('GET','/api/m02/fetch'),('POST','/api/m03/print'),('PUT','/api/m14/config'),('GET','/api/m03/notices/1/pdf')]:
            assert client.request(method,path).status_code==403
        assert calls==[]
        assert client.post('/api/m05/history/save').status_code==200
        assert calls==['local']
