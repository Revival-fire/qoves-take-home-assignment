
## Kubernetes Platform Operations Writeup

## Overview

## CNI Decision

### Choice
Calico

### Why

Minikube's default CNI does not enforce Kubernetes NetworkPolicy.
Calico was selected because it provides production-grade
network policy enforcement and supports ingress and egress controls.

### Tradeoff

Calico introduces additional networking components compared
to the default CNI, but the security benefits justify the
operational complexity.

This document explains the operational decisions, deployment model, production considerations, and recovery procedures for the Qoves API Kubernetes deployment.

The platform uses:

- Kubernetes (Minikube)
- Calico CNI
- ArgoCD GitOps
- PostgreSQL StatefulSet
- Kubernetes Persistent Volumes
- Sealed Secrets
- Kubernetes NetworkPolicies
- NGINX Ingress
- Prometheus monitoring


---

# 1. Run It

## Repository Layout

The repository follows a GitOps structure where application code and Kubernetes deployment configuration are version-controlled separately.


```text
qoves-take-home-assignment/
│
├── app/
│   ├── app.py
│   ├── requirements.txt
│   └── Dockerfile
│
├── gitops/
│   ├── root-app.yaml
│   │
│   ├── namespaces/
│   │   └── namespace.yaml
│   │
│   ├── postgres/
│   │   ├── pvc.yaml
│   │   ├── secret-sealed.yaml
│   │   ├── service.yaml
│   │   └── statefulset.yaml
│   │
│   ├── api/
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   ├── ingress.yaml
│   │   ├── hpa.yaml
│   │   └── networkpolicy.yaml
│   │
│   ├── monitoring/
│   │   ├── prometheus.yaml
│   │   ├── servicemonitor.yaml
│   │   └── alert-rules.yaml
│   │
│   └── applications/
│       ├── api-app.yaml
│       ├── postgres-app.yaml
│       ├── monitoring-app.yaml
│       └── namespace-app.yaml
│
└── README.md
```

# Stand Up From Scratch

## 1. Create Kubernetes Cluster

Create a two-node Minikube cluster using Calico:


```bash
minikube start --nodes=2 --cni=calico
```



Enable Kubernetes addons:


minikube addons enable ingress

minikube addons enable metrics-server



---

## 2. Install Platform Controllers

Install ArgoCD:


kubectl create namespace argocd

kubectl apply
-f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml



Install Sealed Secrets:


kubectl apply
-f https://github.com/bitnami-labs/sealed-secrets/releases/latest/download/controller.yaml



These components are installed manually because they bootstrap the GitOps control plane.


---

## 3. Deploy Through GitOps

After ArgoCD is available, only the root application is applied manually:


kubectl apply
-f gitops/root-app.yaml



The root application points to:


gitops/applications/



ArgoCD then creates child applications:


namespace application

    |
    |

postgres application

    |
    |

api application

    |
    |

monitoring application



All workload deployments are now managed by Git.


---

# Making a Change

Example:

Increase API replicas:

Before:

```yaml
replicas: 2

Change:

replicas: 4

Commit:

git add .

git commit -m "scale API deployment"

git push

Flow:

Developer

   |
   |

Git commit

   |
   |

GitHub repository

   |
   |

ArgoCD detects drift

   |
   |

Kubernetes updated automatically

No manual kubectl deployment is required.

2. Architectural Decisions (ADR)
ADR 001 - CNI Selection
Decision

Use Calico as the Kubernetes CNI.

Alternatives Considered
Default Minikube CNI
Cilium
Reason

Kubernetes NetworkPolicy objects only define the desired security model. They require a CNI implementation to enforce them.

The default Minikube networking does not enforce NetworkPolicy, meaning security policies could exist but have no effect.

Calico was selected because it is mature, widely adopted, supports ingress and egress policies, and provides the network isolation required for this assignment.

Cilium would also have been a valid choice and provides additional eBPF-based visibility, but Calico provides a simpler operational model for this environment.

ADR 002 - Secret Management
Decision

Use Bitnami Sealed Secrets.

Alternatives Considered
Plain Kubernetes Secrets
SOPS
External Secrets Operator
Reason

Plain Kubernetes Secrets are only base64 encoded and should not be committed to Git.

SOPS is secure but requires additional tooling and ArgoCD integration.

External Secrets Operator is preferred in production when connected to a real secret backend such as AWS Secrets Manager or Hashicorp Vault.

For a local Kubernetes environment, Sealed Secrets provides the simplest secure GitOps workflow:

encrypted secret

        |

Git repository

        |

Sealed Secrets Controller

        |

Kubernetes Secret

The application receives credentials only at runtime.

ADR 003 - PostgreSQL Deployment Model
Decision

Deploy PostgreSQL using a StatefulSet with PersistentVolume storage.

Alternatives Considered
Kubernetes Deployment
CloudNativePG Operator
External managed database
Reason

A Deployment is designed for stateless workloads and does not provide stable identity or storage behavior.

CloudNativePG would provide better production PostgreSQL lifecycle management including backups, replication, and failover.

However, for this local assignment a StatefulSet demonstrates the fundamental Kubernetes primitives:

stable network identity
persistent storage
controlled startup

In production I would prefer a PostgreSQL operator or managed database service.

ADR 004 - Scaling Signal
Decision

Use CPU utilization based Horizontal Pod Autoscaling.

Alternatives Considered
Request per second
Response latency
Queue depth
Database connections
Reason

CPU utilization is simple and supported natively by Kubernetes metrics-server.

For this small HTTP API it is acceptable.

However, CPU is not always the best scaling signal.

For a production API handling real user traffic, I would prefer:

HTTP requests per second
latency percentile
active connections
background job queue depth

because those metrics represent user demand more accurately.

3. What Minikube Provided For Me

Minikube provides a complete Kubernetes environment locally.

On real bare metal or self-managed infrastructure, these responsibilities would become platform engineering tasks.

Control Plane Bootstrap

Minikube automatically created:

Kubernetes API server
Scheduler
Controller Manager
CoreDNS
etcd

In a bare-metal environment I would need to bootstrap these components using tools such as:

kubeadm
Rancher
Kubespray

I would also need to manage:

certificates
cluster upgrades
API availability
CNI Installation

Minikube installed Calico automatically.

In bare metal Kubernetes I would manually deploy:

CNI manifests
node networking components
IP allocation configuration

The CNI is responsible for:

pod networking
service communication
NetworkPolicy enforcement
Ingress Load Balancing

Minikube provided the NGINX ingress controller.

In production bare metal I would need to provide:

ingress controller
external IP assignment
load balancer integration

Examples:

MetalLB
HAProxy
F5
cloud load balancers
Storage Provisioner

Minikube provides a local storage provisioner.

This automatically creates PersistentVolumes.

Production requires:

CSI drivers
storage classes
replication strategy

Examples:

AWS EBS CSI
Ceph
Longhorn
NetApp
etcd and Backup

Minikube manages etcd internally.

Production Kubernetes requires:

etcd cluster management
encryption at rest
snapshots
restore testing

Example backup:

ETCDCTL_API=3 etcdctl snapshot save backup.db
4. Production Gaps

This deployment demonstrates Kubernetes fundamentals but is not production ready.

The following improvements are required.

High Availability

Current:

1 PostgreSQL replica
1 Prometheus replica

Production requires:

multiple Kubernetes control-plane nodes
PostgreSQL replication
distributed monitoring
Database Backups

Current:

PVC persistence only.

Missing:

automated backups
point-in-time recovery
restore testing

Production solution:

CloudNativePG backups
pgBackRest
S3 object storage
Real Secret Backend

Current:

Sealed Secrets.

Production:

Use:

AWS Secrets Manager
Hashicorp Vault
Azure Key Vault
Google Secret Manager

The application should retrieve secrets dynamically rather than storing encrypted objects in Git.

Cluster Upgrades

Missing:

Kubernetes version upgrade strategy
node draining
compatibility testing

Production process:

upgrade control plane

        |

upgrade worker nodes

        |

validate workloads
Multi Cluster

Current:

Single Minikube cluster.

Production:

Separate:

Development cluster

        |

Staging cluster

        |

Production cluster

Managed by:

ArgoCD ApplicationSets
Terraform
Cluster API
5. Failure Runbook
Scenario: Database Pod Failure

Problem:

postgres-0

is unavailable.

Detection

Prometheus alert:

QovesAPIHighHealthFailures

Symptoms:

GET /healthz

returns 503
Step 1 - Check PostgreSQL Status
kubectl get pods -n qoves-app

Expected:

postgres-0   CrashLoopBackOff
Step 2 - Inspect Logs
kubectl logs postgres-0 \
-n qoves-app

Check for:

disk errors
configuration issues
corruption
Step 3 - Verify Storage

Check PVC:

kubectl get pvc \
-n qoves-app

Expected:

postgres-data Bound

The PVC should remain available even if the pod dies.

Step 4 - Recover Through Git Where Possible

If the issue is configuration related:

Fix the StatefulSet:

git commit -m "fix postgres configuration"

git push

ArgoCD reconciles:

Git

 |

ArgoCD

 |

Kubernetes
Step 5 - Force Pod Recreation

If required:

kubectl delete pod postgres-0 \
-n qoves-app

StatefulSet recreates:

postgres-0

and reattaches:

postgres-data PVC
Step 6 - Validate Recovery

Check:

kubectl get pods -n qoves-app

Test:

curl http://qoves.local/healthz

Expected:

HTTP 200

database reachable
Summary

This platform demonstrates:

Kubernetes networking
GitOps delivery
secure secret handling
persistent workloads
observability
operational recovery

The design intentionally separates:

Application code

from

Infrastructure delivery

allowing safe, auditable, and repeatable deployments.