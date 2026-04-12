terraform {
  required_version = ">= 1.5.0"

  required_providers {
    signoz = {
      source  = "Signoz/signoz"
      version = "~> 0.0.4"
    }
  }
}

provider "signoz" {
  endpoint     = var.signoz_endpoint
  access_token = var.signoz_access_token
}
