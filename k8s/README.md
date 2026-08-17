# Local Kubernetes runbook

The API runs with three replicas and scales to ten replicas at 50% average CPU.
The in-process scheduler is disabled in API pods and runs in exactly one separate pod.

## Prerequisites

- Docker Desktop with Kubernetes enabled
- `kubectl`
- Metrics Server (`kubectl top pods` must return metrics)
- The PostgreSQL, Dify, and TransNews addresses in `.env` must be reachable from pods

For Docker Desktop, host services should normally use `host.docker.internal` rather than
`localhost` in `.env`.

Before creating the Secret, make sure `.env` contains every required setting from
`.env.example`. In particular, the current application requires these Dify values even
when the corresponding endpoint is not used:

```text
CHATFLOW_API_KEY
SUMMARY_WORKFLOW_API_KEY
SCORING_WORKFLOW_API_KEY
ANALYSIS_WORKFLOW_API_KEY
KNOWLEDGE_API_KEY
DIFY_DATASET_ID
DIFY_ARTICLE_ID_METADATA_FIELD_ID
```

## Deploy

Run from the repository root:

```powershell
docker build -t news-monitor-api:local .
kubectl apply -f k8s/namespace.yaml
kubectl create secret generic news-api-env -n news-monitor --from-env-file=.env --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f k8s/api-deployment.yaml
kubectl apply -f k8s/api-service.yaml
kubectl apply -f k8s/api-hpa.yaml
kubectl apply -f k8s/scheduler-deployment.yaml
kubectl rollout status deployment/news-api -n news-monitor
kubectl port-forward service/news-api -n news-monitor 8001:8001
```

Do not commit a rendered Secret or the real `.env` file.

## Observe replicas and traffic

In separate terminals:

```powershell
kubectl get hpa,pods -n news-monitor -w
kubectl top pods -n news-monitor
```

Repeated calls to `http://localhost:8001/` return the serving pod name. A new HTTP
connection per request makes distribution easier to observe.

Generate load with an installed load generator, for example:

```powershell
hey -z 5m -c 100 http://localhost:8001/api/v1/articles
```

Use an endpoint that performs enough work to raise CPU. HPA reacts to sustained metrics,
so scaling is not instantaneous.

## Remove the local deployment

```powershell
kubectl delete namespace news-monitor
```
