from google.cloud import bigquery
from google.oauth2 import service_account
import streamlit as st

@st.cache_resource
def get_client():
    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"]
    )
    return bigquery.Client(
        credentials=credentials,
        project="training-assistant-prod"
    )

def query(sql, params=None):
    client = get_client()
    if params:
        job_config = bigquery.QueryJobConfig(
            query_parameters=params
        )
        return client.query(sql, job_config=job_config).to_dataframe()
    return client.query(sql).to_dataframe()

def insert_rows(table_id, rows):
    client = get_client()
    table = client.get_table(table_id)
    errors = client.insert_rows(table, rows)
    if errors:
        raise Exception(f"BigQuery insert error: {errors}")
    return True