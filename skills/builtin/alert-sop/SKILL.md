---
name: alert-sop
description: Analyze alert messages with a structured incident/SOP workflow and produce a concise handling report.
trigger: user provides an alert, incident signal, monitoring message, outage symptom, error spike, latency warning, resource warning, or asks for alert triage/SOP handling
do-not-trigger: user only discusses alerting concepts without a concrete alert or incident context
user-invocable: true
disable-auto-invoke: false
argument-hint: <alert text, metrics, timeline, affected service, and available evidence>
blocked-tools:
  - execute_office_shell
tags:
  - ops
  - alert
  - sop
  - abu-migrated
---

# Alert SOP

Use this skill to triage a concrete alert or incident signal.

## Steps

1. Classify severity:
   - P0: service unavailable, data loss, security incident, widespread 5xx.
   - P1: severe latency, high error rate, resource exhaustion, major customer impact.
   - P2: degraded business metric, partial feature issue, warning threshold.

2. Gather facts from the user-provided evidence:
   - Alert content and timestamp.
   - Affected service, region, customer segment, or dependency.
   - Recent deploys or configuration changes.
   - Error logs, dashboards, or metric changes if supplied.

3. Analyze likely cause:
   - Deploy-correlated issue.
   - Dependency outage.
   - Traffic or workload spike.
   - Capacity/resource exhaustion.
   - Scheduled job or batch interference.

4. Report:
   - Summary.
   - Severity.
   - Evidence.
   - Likely cause.
   - Recommended action.
   - Unknowns and next checks.

Do not invent logs, dashboards, deploys, owners, or recovery status.
