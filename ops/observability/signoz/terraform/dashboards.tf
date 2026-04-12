locals {
  dashboard_files = fileset("${path.module}/../dashboards", "*.json")
  dashboards = {
    for dashboard_file in local.dashboard_files :
    trimsuffix(basename(dashboard_file), ".json") => jsondecode(
      file("${path.module}/../dashboards/${dashboard_file}")
    )
  }
}

resource "signoz_dashboard" "pathfinder" {
  for_each = local.dashboards

  collapsable_rows_migrated = lookup(each.value, "collapsable_rows_migrated", true)
  description               = each.value.description
  name                      = each.value.name
  title                     = each.value.title
  version                   = each.value.version
  uploaded_grafana          = lookup(each.value, "uploaded_grafana", false)
  tags                      = lookup(each.value, "tags", [])
  layout                    = jsonencode(each.value.layout)
  variables                 = jsonencode(lookup(each.value, "variables", {}))
  widgets                   = jsonencode(each.value.widgets)
  panel_map                 = jsonencode(lookup(each.value, "panel_map", {}))
}

output "pathfinder_dashboard_ids" {
  value = {
    for key, dashboard in signoz_dashboard.pathfinder :
    key => dashboard.id
  }
}
