{{/*
Expand the name of the chart.
*/}}
{{- define "pdf-to-podcast.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "pdf-to-podcast.fullname" -}}
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
{{- define "pdf-to-podcast.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "pdf-to-podcast.labels" -}}
helm.sh/chart: {{ include "pdf-to-podcast.chart" . }}
{{ include "pdf-to-podcast.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "pdf-to-podcast.selectorLabels" -}}
app.kubernetes.io/name: {{ include "pdf-to-podcast.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Image pull policy
*/}}
{{- define "pdf-to-podcast.imagePullPolicy" -}}
{{- .Values.imagePullPolicy | default "IfNotPresent" }}
{{- end }}

{{/*
Redis host (standalone deployment)
*/}}
{{- define "pdf-to-podcast.redisHost" -}}
{{- printf "redis" }}
{{- end }}

{{/*
MinIO endpoint (from subchart)
*/}}
{{- define "pdf-to-podcast.minioEndpoint" -}}
{{- printf "minio:9000" }}
{{- end }}

{{/*
Jaeger OTLP endpoint (from Jaeger subchart)
*/}}
{{- define "pdf-to-podcast.jaegerOtlpEndpoint" -}}
{{- printf "http://%s-jaeger-collector:4317" .Release.Name }}
{{- end }}
