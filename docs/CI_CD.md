# CI/CD Pipeline Design

This document outlines the CI/CD strategy for Annotex, including design decisions, security principles, and implementation details.

---

## Project Context

| Aspect | Details |
|--------|---------|
| Language | Python 3.11 |
| Framework | FastAPI |
| Database | PostgreSQL (prod), SQLite (CI tests) |
| Queue | Redis + Celery |
| Container | Docker |
| Registry | DockerHub |
| Deployment Target | AWS EKS (Kubernetes) |

---

## CI Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CI PIPELINE                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐  │
│  │ Checkout │ → │  Setup   │ → │  Lint    │ → │  SAST    │ → │   SCA    │  │
│  │          │   │ Python   │   │ (Ruff)   │   │ (CodeQL/ │   │(pip-audit)│  │
│  │          │   │          │   │          │   │  Bandit) │   │          │  │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘  │
│                                                                              │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐  │
│  │  Tests   │ → │  Build   │ → │  Docker  │ → │  Trivy   │ → │ Runtime  │  │
│  │ (Pytest) │   │ (Verify) │   │  Build   │   │  Scan    │   │  Test    │  │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘  │
│                                                                              │
│                              ┌──────────┐                                    │
│                              │  Push to │                                    │
│                              │ DockerHub│                                    │
│                              └──────────┘                                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## CI Stages Explained

### Why Each Stage Exists

| Stage | Tool | Purpose | Risk Mitigated |
|-------|------|---------|----------------|
| **Checkout** | `actions/checkout` | Retrieve source code from repository | None - prerequisite for all stages |
| **Setup Python** | `actions/setup-python` | Install consistent Python version | "Works on my machine" syndrome |
| **Dependency Cache** | `actions/cache` | Cache pip packages between runs | Slow CI feedback loops (5min → 30sec) |
| **Linting** | `ruff` | Enforce coding standards, catch syntax errors | Technical debt, inconsistent code style |
| **SAST** | `CodeQL` + `bandit` | Static analysis for security vulnerabilities | SQL injection, XSS, hardcoded secrets, OWASP Top 10 |
| **SCA** | `pip-audit` | Scan dependencies for known vulnerabilities | Supply chain attacks (e.g., compromised packages) |
| **Unit Tests** | `pytest` | Validate business logic correctness | Regressions, broken features shipping to prod |
| **Build Verify** | Import check | Ensure application can start without errors | Deployment failures due to missing imports |
| **Docker Build** | `docker build` | Create container image | Environment inconsistencies between dev/prod |
| **Image Scan** | `trivy` | Scan container for OS/library vulnerabilities | Shipping containers with known CVEs |
| **Runtime Test** | `docker run` + healthcheck | Verify container actually runs and responds | Image builds successfully but crashes at runtime |
| **Registry Push** | `docker push` | Publish verified image to DockerHub | Enables CD pipeline to pull trusted images |

---

## Tool Selection (Python Equivalents)

| Purpose | Java Tool | Python Tool | Why This Choice |
|---------|-----------|-------------|-----------------|
| Linting | Checkstyle | **Ruff** | 10-100x faster than flake8, combines multiple linters |
| Formatting | - | **Ruff** (or Black) | Consistent code style |
| SAST | CodeQL | **CodeQL + Bandit** | CodeQL for GitHub integration, Bandit for Python-specific checks |
| SCA | OWASP Dependency-Check | **pip-audit** | Official PyPI vulnerability database |
| Testing | JUnit | **Pytest** | De facto Python testing standard |
| Coverage | JaCoCo | **pytest-cov** | Integrated with pytest |
| Container Scan | Trivy | **Trivy** | Language-agnostic, excellent CVE database |

---

## CD Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CD PIPELINE                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐  │
│  │ Trigger  │ → │Configure │ → │  Deploy  │ → │  DAST    │ → │  Notify  │  │
│  │(manual / │   │  AWS +   │   │  to EKS  │   │ (OWASP   │   │ (GitHub  │  │
│  │workflow_ │   │  kubectl │   │          │   │   ZAP)   │   │ Summary) │  │
│  │dispatch) │   │          │   │          │   │          │   │          │  │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### CD Stages Explained

| Stage | Purpose | Risk Mitigated |
|-------|---------|----------------|
| **Trigger** | Manual trigger or after CI passes on `main` | Controlled deployments |
| **Configure AWS** | Authenticate with AWS EKS | Unauthorized deployments |
| **Deploy to EKS** | Apply Kubernetes manifests | Manual deployment errors |
| **DAST** | Dynamic security testing on running app | Runtime vulnerabilities not caught by SAST |
| **Notify** | Report deployment status in GitHub | Unnoticed failures |

---

## Shift-Left Security

### Traditional vs Shift-Left Approach

```
Traditional Pipeline:
┌──────┐   ┌──────┐   ┌──────┐   ┌──────┐   ┌──────┐
│ Code │ → │Build │ → │ Test │ → │Deploy│ → │ Scan │
└──────┘   └──────┘   └──────┘   └──────┘   └──────┘
                                                 ↑
                                          Security scan
                                          (Too late! Already deployed)

Shift-Left Pipeline (Our Approach):
┌──────┐   ┌──────┐   ┌──────┐   ┌──────┐   ┌──────┐   ┌──────┐   ┌──────┐
│ Code │ → │ Lint │ → │ SAST │ → │ SCA  │ → │ Test │ → │Build │ → │ Scan │
└──────┘   └──────┘   └──────┘   └──────┘   └──────┘   └──────┘   └──────┘
               ↑          ↑          ↑
         Security checks moved LEFT (earlier in pipeline)
         Catch issues before they reach production
```

### Why Shift-Left Matters

| When Caught | Cost to Fix | Example |
|-------------|-------------|---------|
| During coding | $1 | IDE shows error |
| In CI pipeline | $10 | PR blocked, dev fixes |
| In staging | $100 | QA finds bug, sprint delayed |
| In production | $1000+ | Customer impact, emergency fix |

**Key Principle:** Find bugs and vulnerabilities as early as possible.

---

## GitHub Secrets Required

| Secret | Purpose | Where Used |
|--------|---------|------------|
| `DOCKERHUB_USERNAME` | Docker registry username | CI - Push image |
| `DOCKERHUB_TOKEN` | Docker registry access token | CI - Push image |
| `AWS_ACCESS_KEY_ID` | AWS authentication | CD - EKS deployment |
| `AWS_SECRET_ACCESS_KEY` | AWS authentication | CD - EKS deployment |

### Security Note
- NEVER hardcode secrets in code or YAML
- Use GitHub Secrets for all sensitive values
- Rotate tokens regularly
- Use minimal-permission IAM roles for AWS

---

## File Structure

```
annotex/
├── .github/
│   └── workflows/
│       ├── ci.yml              # CI pipeline (build, test, scan, push)
│       └── cd.yml              # CD pipeline (deploy to EKS)
├── k8s/                        # Kubernetes manifests
│   ├── deployment.yml
│   ├── service.yml
│   ├── configmap.yml
│   └── secrets.yml
├── app/                        # Application code
├── tests/                      # Test suite
├── docs/                       # Documentation
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## CI Testing Strategy

### Database Choice for CI

| Environment | Database | Why |
|-------------|----------|-----|
| CI Pipeline | SQLite | Fast, no external service needed, in-memory option |
| Local Dev | PostgreSQL (Docker) | Match production behavior |
| Production | PostgreSQL (RDS) | Scalable, managed |

### Test Categories

| Type | Purpose | When Run |
|------|---------|----------|
| Unit Tests | Test individual functions | Every CI run |
| Integration Tests | Test API endpoints | Every CI run |
| E2E Tests | Test full user flows | Before release |

---

## Branch Strategy

### Chosen Strategy: CI on PRs + Push to `main`

This project uses **Strategy 2: CI on PRs + Push to main** for the following reasons:
- Code review is enforced before merging
- `main` branch is always stable and deployable
- Bad code is blocked before it reaches `main`
- Standard industry practice for team projects

### Workflow Diagram

```
feature-branch                         main
     │                                   │
     │  ┌───────────────────────────┐    │
     └──│     Pull Request (PR)     │────┘
        └───────────────────────────┘
                    │
                    ▼
           CI runs on PR
        (lint, test, SAST, SCA)
                    │
                    ▼
            ┌───────────────┐
            │ CI Passes?    │
            └───────────────┘
               │         │
              Yes        No
               │         │
               ▼         ▼
         Code Review   PR Blocked
               │       (fix issues)
               ▼
        Merge to main
               │
               ▼
      CI runs again on main
    (build, scan, push image)
               │
               ▼
      Image pushed to DockerHub
```

### GitHub Actions Trigger Configuration

```yaml
on:
  pull_request:
    branches: [main]
  push:
    branches: [main]
```

### Branch Strategy Options Comparison

#### Strategy 1: CI on Every Push to `main`

```
Developer pushes directly to main
         │
         ▼
    ┌─────────┐
    │  main   │ ──→ CI runs ──→ Build ──→ Push to DockerHub
    └─────────┘
```

| Aspect | Details |
|--------|---------|
| **How it works** | Developers push directly to `main`, CI triggers on every push |
| **Pros** | Simple, minimal setup, fast feedback |
| **Cons** | Broken code can reach `main`, no review process, risky for production |
| **When to use** | Solo projects, early prototypes, personal learning projects |

---

#### Strategy 2: CI on PRs + Push to `main` ✅ (SELECTED)

```
feature-branch                    main
     │                             │
     │  ┌─────────────────────┐    │
     └──│  Pull Request (PR)  │────┘
        └─────────────────────┘
                 │
                 ▼
        CI runs on PR ──→ Review ──→ Merge ──→ CI runs again ──→ Push image
        (tests, lint,      │
         security scan)    │
                           │
              PR blocked if CI fails
```

| Aspect | Details |
|--------|---------|
| **How it works** | Feature branches → PR → CI runs → Review → Merge → CI runs on main |
| **Pros** | Code review enforced, `main` always stable, team collaboration |
| **Cons** | Slightly slower (need PR for everything), requires discipline |
| **When to use** | Team projects (2+ devs), production apps, open source, **most common in industry** |

---

#### Strategy 3: CD Only on Tags (Release-based)

```
main branch                              Tags
    │                                      │
    │  (CI runs on every push/PR)          │
    │                                      │
    │         git tag v1.0.0               │
    │──────────────────────────────────────│
                                           │
                                           ▼
                              CD Pipeline triggers
                                           │
                                           ▼
                              Deploy to Production (EKS)
```

| Aspect | Details |
|--------|---------|
| **How it works** | CI on PRs/pushes, CD triggers only on version tags (`v1.0.0`) |
| **Pros** | Explicit deploy control, version history, easy rollback |
| **Cons** | Extra step to create tags, not fully continuous deployment |
| **When to use** | Production systems, regulated industries, when approval needed before deploy |

---

### Strategy Comparison Table

| Aspect | Push to Main | PR + Main ✅ | Tags for CD |
|--------|--------------|--------------|-------------|
| **Code Review** | No | Yes | Yes |
| **Main Stability** | Risky | Stable | Stable |
| **Deploy Control** | Automatic | Automatic | Manual trigger |
| **Rollback** | Hard | Medium | Easy (tag versions) |
| **Team Size** | Solo | 2+ devs | Any |
| **Complexity** | Low | Medium | Medium |
| **Industry Usage** | Rare | **Common** | Common |

---

### Why Strategy 2 for Annotex

1. **Code Quality**: Every change is reviewed before merging
2. **Stability**: `main` is always in a deployable state
3. **Collaboration**: Team members can review and discuss changes
4. **CI Feedback**: Issues caught before merge, not after
5. **Industry Standard**: Aligns with professional development practices

---

## Deployment Environments

| Environment | Trigger | Purpose |
|-------------|---------|---------|
| CI (Testing) | PR to `main` | Run tests, linting, security scans |
| CI (Build) | Push to `main` | Build image, push to DockerHub |
| Production | Manual / CD pipeline | Deploy to AWS EKS |

---

## Success Metrics

| Metric | Target | Why |
|--------|--------|-----|
| CI Duration | < 10 minutes | Fast feedback loop |
| Test Coverage | > 80% | Confidence in changes |
| Security Scan Pass | 0 critical/high CVEs | Secure deployments |
| Deployment Frequency | Multiple per week | Agile delivery |

---

## References

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Trivy Documentation](https://aquasecurity.github.io/trivy/)
- [AWS EKS Best Practices](https://aws.github.io/aws-eks-best-practices/)
