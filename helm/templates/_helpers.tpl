{{/*
Expand the name of the chart.
*/}}
{{- define "stac-auth-proxy.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "stac-auth-proxy.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "stac-auth-proxy.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "stac-auth-proxy.labels" -}}
helm.sh/chart: {{ include "stac-auth-proxy.chart" . }}
{{ include "stac-auth-proxy.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "stac-auth-proxy.selectorLabels" -}}
app.kubernetes.io/name: {{ include "stac-auth-proxy.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "stac-auth-proxy.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "stac-auth-proxy.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Render env var value based on type
*/}}
{{- define "stac-auth-proxy.envValue" -}}
{{- if kindIs "string" . -}}
  {{- . | quote -}}
{{- else -}}
  {{- . | toJson | quote -}}
{{- end -}}
{{- end -}}

{{/*
Generate authorization environment variables
*/}}
{{- define "stac-auth-proxy.authorizationEnv" -}}
{{- $routeMode := .Values.authorization.route.mode | default "default" -}}
{{- $recordMode := .Values.authorization.record.mode | default "disabled" -}}

{{- /* Route-level authorization */ -}}
{{- if eq $routeMode "default" -}}
{{- if not (hasKey .Values.env "DEFAULT_PUBLIC") }}
- name: DEFAULT_PUBLIC
  value: "true"
{{- end }}
{{- else if eq $routeMode "custom" -}}
{{- if not (hasKey .Values.env "DEFAULT_PUBLIC") }}
- name: DEFAULT_PUBLIC
  value: {{ .Values.authorization.route.defaultPublic | quote }}
{{- end }}
{{- if and .Values.authorization.route.publicEndpoints (not (hasKey .Values.env "PUBLIC_ENDPOINTS")) }}
- name: PUBLIC_ENDPOINTS
  value: {{ .Values.authorization.route.publicEndpoints | toJson | quote }}
{{- end }}
{{- if and .Values.authorization.route.privateEndpoints (not (hasKey .Values.env "PRIVATE_ENDPOINTS")) }}
- name: PRIVATE_ENDPOINTS
  value: {{ .Values.authorization.route.privateEndpoints | toJson | quote }}
{{- end }}
{{- end }}

{{- /* Record-level authorization */ -}}
{{- if eq $recordMode "custom" -}}
{{- if not (hasKey .Values.env "COLLECTIONS_FILTER_CLS") }}
- name: COLLECTIONS_FILTER_CLS
  value: "stac_auth_proxy.custom_filters:CollectionsFilter"
{{- end }}
{{- if not (hasKey .Values.env "ITEMS_FILTER_CLS") }}
- name: ITEMS_FILTER_CLS
  value: "stac_auth_proxy.custom_filters:ItemsFilter"
{{- end }}
{{- else if eq $recordMode "opa" -}}
{{- if not (hasKey .Values.env "ITEMS_FILTER_CLS") }}
- name: ITEMS_FILTER_CLS
  value: "stac_auth_proxy.filters.opa:Opa"
{{- end }}
{{- if not (hasKey .Values.env "ITEMS_FILTER_ARGS") }}
- name: ITEMS_FILTER_ARGS
  value: {{ list .Values.authorization.record.opa.url .Values.authorization.record.opa.policy | toJson | quote }}
{{- end }}
{{- end }}
{{- end -}}

{{/*
Generate authorization volumes
*/}}
{{- define "stac-auth-proxy.authorizationVolumes" -}}
{{- if and (eq (.Values.authorization.record.mode | default "disabled") "custom") .Values.authorization.record.custom.filtersFile }}
- name: custom-filters
  configMap:
    name: {{ include "stac-auth-proxy.fullname" . }}-filters
{{- end }}
{{- end -}}

{{/*
Generate authorization volume mounts
*/}}
{{- define "stac-auth-proxy.authorizationVolumeMounts" -}}
{{- if and (eq (.Values.authorization.record.mode | default "disabled") "custom") .Values.authorization.record.custom.filtersFile }}
- name: custom-filters
  mountPath: /app/src/stac_auth_proxy/custom_filters.py
  subPath: custom_filters.py
  readOnly: true
{{- end }}
{{- end -}}
