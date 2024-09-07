import os
import logging
from flask import Flask, jsonify
from google.cloud import storage, secretmanager, bigquery
from google.auth import default
from google.auth.exceptions import DefaultCredentialsError
from langchain_openai import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
import yaml

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# get project ID
project_id = os.environ.get("GCP_PROJECT")
if not project_id:
    try:
        _, project_id = default()
    except DefaultCredentialsError:
        logging.error("unable to retrieve default credentials")
    except Exception as e:
        logging.error(f"error determining project ID: {str(e)}")

if not project_id:
    logging.error("project ID is not set")
else:
    logging.info(f"project ID: {project_id}")

# initialize clients
try:
    storage_client = storage.Client(project=project_id)
    bigquery_client = bigquery.Client(project=project_id)
    secret_client = secretmanager.SecretManagerServiceClient()
    logging.info("clients initialized successfully")
except Exception as e:
    logging.error(f"error initializing clients: {str(e)}")

# get OpenAI API key from Secret Manager
openai_api_key = None
if project_id:
    try:
        secret_name = f"projects/{project_id}/secrets/openai_api_key/versions/latest"
        logging.info(f"attempting to access secret: {secret_name}")
        response = secret_client.access_secret_version(request={"name": secret_name})
        openai_api_key = response.payload.data.decode("UTF-8")
        logging.info("successfully retrieved OpenAI API key")
    except Exception as e:
        logging.error(f"error accessing secret: {str(e)}")
else:
    logging.error("cannot access secret: Project ID is not set")

# initialize OpenAI embeddings
embeddings = None
if openai_api_key:
    try:
        embeddings = OpenAIEmbeddings(model="text-embedding-3-large", api_key=openai_api_key)
        logging.info("OpenAI embeddings initialized successfully")
    except Exception as e:
        logging.error(f"error initializing OpenAI embeddings: {str(e)}")
else:
    logging.error("cannot initialize OpenAI embeddings: API key is not set")

# initialize text splitter
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

def process_yaml_file(bucket_name, file_name):
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(file_name)
    content = blob.download_as_text()
    semantic_model = yaml.safe_load(content)
    entity_name = semantic_model['semantic_model']['name']
    return entity_name, yaml.dump(semantic_model)

def insert_embeddings_to_bigquery(entity_name, rows_to_insert):
    dataset_id = os.environ.get('BIGQUERY_DATASET', 'knowledge_base')
    table_id = os.environ.get('BIGQUERY_TABLE', 'semantic_model_vector')
    table_ref = f"{bigquery_client.project}.{dataset_id}.{table_id}"

    # delete existing rows for the processed entity
    delete_query = f"""
    DELETE FROM `{table_ref}`
    WHERE entity = @entity
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("entity", "STRING", entity_name)
        ]
    )
    bigquery_client.query(delete_query, job_config=job_config).result()

    # insert new rows
    errors = bigquery_client.insert_rows_json(table_ref, rows_to_insert)

    if errors:
        raise Exception(f"errors occurred while uploading embeddings for {entity_name}: {errors}")

def process_file(bucket_name, file_name):
    entity_name, yaml_content = process_yaml_file(bucket_name, file_name)
    texts = text_splitter.split_text(yaml_content)
    embedded_texts = embeddings.embed_documents(texts)

    rows_to_insert = [
        {
            "entity": entity_name,
            "chunk_id": f"{entity_name}_{i}",
            "text_chunk": chunk,
            "embedding": embedding
        }
        for i, (chunk, embedding) in enumerate(zip(texts, embedded_texts))
    ]

    insert_embeddings_to_bigquery(entity_name, rows_to_insert)
    return entity_name

@app.route('/run', methods=['POST'])
def process_knowledge_base():
    if not project_id:
        return jsonify({"error": "project ID is not set"}), 500
    if not openai_api_key:
        return jsonify({"error": "OpenAI API key is not set"}), 500
    if not embeddings:
        return jsonify({"error": "OpenAI embeddings are not initialized"}), 500

    try:
        bucket_name = os.environ.get('STORAGE_BUCKET', 'ai-assistant-knowledge-base')
        logging.info(f"attempting to access bucket: {bucket_name}")
        bucket = storage_client.get_bucket(bucket_name)

        processed_files = []
        errors = []

        # list all blobs in the bucket
        blobs = bucket.list_blobs()
        for blob in blobs:
            if blob.name.endswith('.yaml'):
                try:
                    entity_name = process_file(bucket_name, blob.name)
                    processed_files.append(f"{blob.name} ({entity_name})")
                    logging.info(f"processed file: {blob.name}")
                except Exception as e:
                    error_message = f"error processing {blob.name}: {str(e)}"
                    errors.append(error_message)
                    logging.error(error_message)

        if processed_files:
            return jsonify({
                "message": "files processed successfully",
                "processed_files": processed_files,
                "errors": errors
            }), 200
        elif errors:
            return jsonify({
                "message": "errors occurred while processing files",
                "errors": errors
            }), 500
        else:
            return jsonify({
                "message": "no YAML files to process"
            }), 200
    except Exception as e:
        logging.error(f"unexpected error: {str(e)}")
        return jsonify({"error": f"unexpected error: {str(e)}"}), 500

@app.route('/', methods=['GET'])
def hello():
    return f"Hello, World! Project ID: {project_id}", 200

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
