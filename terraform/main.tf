# create Cloud Storage bucket
resource "google_storage_bucket" "ai_assistant_knowledge_base" {
  name     = "ai_assistant_knowledge_base"
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
  project             = var.project
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
