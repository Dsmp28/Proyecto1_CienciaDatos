# ------------------------------------------------------------------------------
# main/budget.tf
# Presupuesto mensual de la cuenta de facturación acotado a este proyecto, con
# alertas por correo al 25 %, 50 %, 75 %, 90 % y 100 % del gasto real, más una
# alerta al 100 % del gasto PRONOSTICADO (avisa antes de llegar).
#
# Costo: 0 USD (presupuestos y canales de notificación por correo son gratuitos).
#
# Requisito de permisos: crear presupuestos exige un rol en la CUENTA DE
# FACTURACIÓN (roles/billing.costsManager o Billing Account Administrator), no
# solo en el proyecto. Si tu usuario no lo tiene, pon `create_budget = false` y
# crea el presupuesto a mano en la consola de Billing.
#
# `credit_types_treatment = EXCLUDE_ALL_CREDITS`: en una cuenta de prueba con
# 300 USD de crédito, el gasto neto sería 0 y las alertas nunca dispararían.
# Excluir créditos hace que el presupuesto mida el consumo real de recursos.
# ------------------------------------------------------------------------------

# Número del proyecto (el filtro del presupuesto exige projects/<número>, no el ID).
data "google_project" "this" {
  count = var.create_budget ? 1 : 0

  project_id = var.project_id
}

# Canal de notificación por correo (Cloud Monitoring).
resource "google_monitoring_notification_channel" "budget_email" {
  count = var.create_budget ? 1 : 0

  project      = var.project_id
  display_name = "Alertas de presupuesto - ${var.project_id}"
  description  = "Recibe las alertas del presupuesto mensual del pipeline de transporte."
  type         = "email"
  enabled      = true

  labels = {
    email_address = var.alert_email
  }

  user_labels = var.labels
}

resource "google_billing_budget" "monthly" {
  count = var.create_budget ? 1 : 0

  billing_account = var.billing_account_id
  display_name    = "Presupuesto mensual ${var.project_id}"

  budget_filter {
    projects               = ["projects/${data.google_project.this[0].number}"]
    credit_types_treatment = "EXCLUDE_ALL_CREDITS"
    calendar_period        = "MONTH"
  }

  amount {
    specified_amount {
      currency_code = "USD"
      units         = tostring(var.budget_amount_usd)
    }
  }

  # Umbrales sobre el gasto real del mes: 0.25, 0.5, 0.75, 0.9, 1.0.
  dynamic "threshold_rules" {
    for_each = local.budget_thresholds
    content {
      threshold_percent = threshold_rules.value
      spend_basis       = "CURRENT_SPEND"
    }
  }

  # Alerta temprana: cuando el pronóstico del mes alcanza el 100 %.
  threshold_rules {
    threshold_percent = 1.0
    spend_basis       = "FORECASTED_SPEND"
  }

  all_updates_rule {
    monitoring_notification_channels = [
      google_monitoring_notification_channel.budget_email[0].id,
    ]
    # false: además del canal de correo, también avisa a los administradores y
    # usuarios de la cuenta de facturación (propietarios) por el mecanismo por defecto.
    disable_default_iam_recipients = false
  }
}
