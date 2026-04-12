variable "signoz_endpoint" {
  description = "SigNoz base URL, for example https://signoz.example.org"
  type        = string
}

variable "signoz_access_token" {
  description = "SigNoz API access token"
  type        = string
  sensitive   = true
}
