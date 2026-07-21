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
Validate terminationGracePeriodSeconds > preStopSleepSeconds
*/}}
{{- define "stac-auth-proxy.validateTerminationGracePeriod" -}}
{{- if not (gt .Values.terminationGracePeriodSeconds .Values.preStopSleepSeconds) -}}
{{- fail "terminationGracePeriodSeconds must be greater than preStopSleepSeconds" -}}
{{- end -}}
{{- end -}}

{{/*
Validate autoscaling replica bounds when HPA is enabled
*/}}
{{- define "stac-auth-proxy.validateAutoscaling" -}}
{{- if .Values.autoscaling.enabled -}}
{{- if lt (int .Values.autoscaling.maxReplicas) (int .Values.autoscaling.minReplicas) -}}
{{- fail "autoscaling.maxReplicas must be greater than or equal to autoscaling.minReplicas" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Health endpoint path: {ROOT_PATH}{HEALTHZ_PREFIX}.
ROOT_PATH trailing slash is trimmed; HEALTHZ_PREFIX defaults to /healthz.
*/}}
{{- define "stac-auth-proxy.healthzPath" -}}
{{- $rootPath := dig "ROOT_PATH" "" .Values.env | default "" | trimSuffix "/" -}}
{{- $healthzPrefix := dig "HEALTHZ_PREFIX" "/healthz" .Values.env | default "/healthz" -}}
{{- printf "%s%s" $rootPath $healthzPrefix -}}
{{- end -}}

{{/*
Render a probe, deriving httpGet.path from ROOT_PATH + HEALTHZ_PREFIX when unset.
Usage: include "stac-auth-proxy.probe" (dict "context" . "probe" .Values.startupProbe)
*/}}
{{- define "stac-auth-proxy.probe" -}}
{{- $result := dict -}}
{{- range $k, $v := .probe -}}
{{- if ne $k "httpGet" -}}
{{- $_ := set $result $k $v -}}
{{- end -}}
{{- end -}}
{{- if .probe.httpGet -}}
{{- $httpGet := dict -}}
{{- range $k, $v := .probe.httpGet -}}
{{- $_ := set $httpGet $k $v -}}
{{- end -}}
{{- if not (hasKey $httpGet "path") -}}
{{- $_ := set $httpGet "path" (include "stac-auth-proxy.healthzPath" .context) -}}
{{- end -}}
{{- $_ := set $result "httpGet" $httpGet -}}
{{- end -}}
{{- toYaml $result -}}
{{- end -}}
