# Set the project for the entire configuration
provider "google" {
  project = var.project
  region  = var.region
}

# create Cloud Storage bucket
resource "google_storage_bucket" "ai_assistant_knowledge_base" {
  name     = "ai_assistant_knowledge_base_${var.project}"
  location = var.region
  uniform_bucket_level_access = true
}

# upload all YAML files from a directory to Cloud Storage
resource "google_storage_bucket_object" "knowledge_base_files" {
  for_each = fileset("${path.module}/../../knowledge_base_files", "*.yaml")
  
  name   = each.value
  bucket = google_storage_bucket.ai_assistant_knowledge_base.name
  source = "${path.module}/../../knowledge_base_files/${each.value}"
}

# create BigQuery dataset
resource "google_bigquery_dataset" "knowledge_base_dataset" {
  dataset_id                 = "knowledge_base"
  friendly_name              = "Shared Knowledge Base"
  description                = "dataset for shared knowledge base"
  location                   = var.region
  delete_contents_on_destroy = true

  labels = {
    environment = "production"
  }

  access {
    role          = "OWNER"
    user_by_email = var.project_owner_email
  }

  access {
    role           = "WRITER"
    user_by_email  = "knowledge-base-sa@${var.project}.iam.gserviceaccount.com"
  }
}

# create a single bigquery table for all embeddings
resource "google_bigquery_table" "knowledge_base_embeddings" {
  dataset_id          = google_bigquery_dataset.knowledge_base_dataset.dataset_id
  table_id            = "semantic_model_embeddings"
  deletion_protection = false

  schema = <<EOF
  [
    {
      "name": "entity",
      "type": "STRING",
      "mode": "REQUIRED",
      "description": "the name of the entity or semantic model"
    },
    {
      "name": "chunk_id",
      "type": "STRING",
      "mode": "REQUIRED",
      "description": "unique identifier for the text chunk"
    },
    {
      "name": "text_chunk",
      "type": "STRING",
      "mode": "REQUIRED",
      "description": "the text content of the chunk"
    },
    {
      "name": "embedding",
      "type": "FLOAT",
      "mode": "REPEATED",
      "description": "the vector embedding of the text chunk"
    }
  ]
EOF
}

# create a secret for the anthropic api key
resource "google_secret_manager_secret" "anthropic_api_key" {
  secret_id = "anthropic-api-key"
  
  replication {
    auto {}
  }
}

# use the existing service account
data "google_service_account" "function_service_account" {
  account_id = "knowledge-base-sa"
}

# grant necessary roles to the existing service account
resource "google_project_iam_member" "function_storage_admin" {
  project = var.project
  role    = "roles/storage.admin"
  member  = "serviceAccount:${data.google_service_account.function_service_account.email}"
}

resource "google_project_iam_member" "function_bigquery_admin" {
  project = var.project
  role    = "roles/bigquery.admin"
  member  = "serviceAccount:${data.google_service_account.function_service_account.email}"
}

# create a zip file of the function source code
data "archive_file" "function_source" {
  type        = "zip"
  source_dir  = "${path.module}/../function"
  output_path = "${path.module}/function-source.zip"
}

# upload the zip file to the bucket
resource "google_storage_bucket_object" "function_source" {
  name   = "function-source-${data.archive_file.function_source.output_md5}.zip"
  bucket = google_storage_bucket.ai_assistant_knowledge_base.name
  source = data.archive_file.function_source.output_path
}

# create the cloud function
resource "google_cloudfunctions_function" "upload_knowledge_base" {
  name        = "upload-knowledge-base"
  description = "function to process and upload knowledge base files"
  runtime     = "python39"

  available_memory_mb   = 256
  source_archive_bucket = google_storage_bucket.ai_assistant_knowledge_base.name
  source_archive_object = google_storage_bucket_object.function_source.name
  trigger_http          = true
  entry_point           = "upload_knowledge_base"
  
  environment_variables = {
    BIGQUERY_DATASET = google_bigquery_dataset.knowledge_base_dataset.dataset_id
    BIGQUERY_TABLE   = google_bigquery_table.knowledge_base_embeddings.table_id
  }

  service_account_email = "knowledge-base-sa@abcdataz.iam.gserviceaccount.com"

  depends_on = [
    google_project_service.cloudfunctions,
    google_project_iam_member.function_storage_admin,
    google_project_iam_member.function_bigquery_admin,
    google_project_iam_member.function_service_account_user
  ]
}

# IAM entry for all users to invoke the function
resource "google_cloudfunctions_function_iam_member" "invoker" {
  cloud_function = google_cloudfunctions_function.upload_knowledge_base.name

  role   = "roles/cloudfunctions.invoker"
  member = "allUsers"
}

output "function_service_account" {
  value = data.google_service_account.function_service_account.email
}

resource "google_project_service" "cloudfunctions" {
  project = var.project
  service = "cloudfunctions.googleapis.com"

  disable_dependent_services = true
  disable_on_destroy         = false
}

resource "google_project_iam_member" "function_service_account_user" {
  project = var.project
  role    = "roles/iam.serviceAccountUser"
  member  = "serviceAccount:${data.google_service_account.function_service_account.email}"
}