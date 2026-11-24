# kubectl dojo

A terminal-based learning game that teaches Kubernetes command-line skills by
walking you through the CKA and CKAD exam curricula, task by task — against a
**real k0s cluster**, not a simulation. Every task is graded by inspecting
actual live cluster state through `kubectl`.

## How it works

- The game presents you a task ("Create a Deployment named `web`...").
- You do the work yourself, in your own terminal, against your k0s cluster.
- You come back to the game and press `c` to check — it runs a set of
  declarative checks (resource exists? right image? right label? RBAC
  actually grants access?) against the cluster and tells you what passed
  or failed.
- Progress is saved locally so you can stop and resume any time.

Content is organized the same way the real exams are:

```
CKA  (25% Cluster Architecture / 15% Workloads & Scheduling /
      20% Services & Networking / 10% Storage / 30% Troubleshooting)
CKAD (20% App Design & Build / 20% App Deployment /
      15% Observability & Maintenance / 25% Environment, Config & Security /
      20% Services & Networking)
```

Each domain is broken into objectives, and each objective into a handful of
concrete, checkable tasks — the same "each step of each objective" structure
you asked for.

## 1. Set up a k0s cluster

If you don't already have one:

```bash
chmod +x scripts/install_k0s.sh
./scripts/install_k0s.sh
export KUBECONFIG=$HOME/.kube/k0s.config     # add to your shell profile too
kubectl get nodes                             # sanity check
```

`install_k0s.sh` auto-detects your OS:

- **Linux**: installs and runs k0s directly on the host, single-node
  (controller + worker combined).
- **macOS**: k0s has no native macOS build, so it delegates to
  `scripts/install_k0s_macos.sh`, which uses [Lima](https://lima-vm.io) (a
  lightweight Linux VM manager, installed via Homebrew if missing) and its
  built-in `template:k0s` preset to run a real k0s cluster inside a small
  Linux VM. The script copies the VM's kubeconfig to `~/.kube/k0s.config`
  automatically — from there, `kubectl` on your Mac talks to it exactly like
  any other cluster. First run downloads a Linux image, so it takes a few
  minutes; after that, `limactl start k0s` / `limactl stop k0s` bring the VM
  up and down quickly.

Already running k0s (on Linux, in a VM, in Lima, etc.)? Just make sure
`KUBECONFIG` points at it (or pass `--kubeconfig` when launching the game) —
everything past this point is identical regardless of how the cluster is
hosted.

## 2. Install the game's Python dependencies

```bash
python3 -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install -r requirements.txt
```

## 3. Play

```bash
python main.py
```

The game will create a `game-lab` namespace on startup and use it as the
default workspace for exercises (each task's prompt says which namespace to
use — a few cluster-scoped tasks, like RBAC ClusterRoles or node taints,
intentionally step outside it).

Useful flags:

```bash
python main.py --kubeconfig /path/to/config   # point at a specific cluster
python main.py --reset-progress               # wipe saved progress and exit
```

In-game, at a task screen:

| Key | Action |
|-----|--------|
| `c` | Run the checks for this task against your live cluster |
| `h` | Show the next hint |
| `r` | Reset this task (runs its cleanup commands, clears its completion) |
| `b` | Back to the task list |
| `q` | Quit |

If you get stuck between attempts and want a clean slate for one task's
resources without losing overall progress, `r` (reset) is your friend. To
nuke the whole lab namespace and start fresh:

```bash
./scripts/reset_environment.sh
```

## Architecture

```
main.py                  # game loop / menu navigation
game/
  models.py               # Task / Objective / Module dataclasses
  content_loader.py        # loads content/*.yaml into those models
  cluster.py               # thin kubectl wrapper (get/list/jsonpath/run)
  validator.py              # dispatches declarative checks -> pass/fail
  progress.py                # JSON-backed completion tracking
  ui.py                        # all rich-based terminal rendering
content/
  cka/*.yaml                # one file per CKA domain
  ckad/*.yaml                # one file per CKAD domain
scripts/
  install_k0s.sh             # single-node k0s installer
  reset_environment.sh        # wipes the game-lab namespace
```

Progress is stored at `~/.k8s_learning_game/progress.json`.

## Extending the content

Everything the game asks you to do lives in the YAML files under `content/`.
No Python changes are needed to add more tasks — just add a new `task:`
entry under the relevant objective:

```yaml
- id: cka-01-rbac-t5           # must be globally unique
  prompt: |
    Create a ClusterRole named `node-viewer` that can get and list nodes.
  hints:
    - "kubectl create clusterrole node-viewer --verb=get,list --resource=nodes"
  cleanup:
    - "kubectl delete clusterrole node-viewer --ignore-not-found"
  checks:
    - type: resource_exists
      kind: clusterrole
      name: node-viewer
  exam_tip: "ClusterRoles aren't namespaced — omit 'namespace' in checks for them."
```

### Available check types (in `game/validator.py`)

| type | purpose |
|------|---------|
| `resource_exists` / `resource_not_exists` | does a named resource exist (or not)? |
| `jsonpath_equals` / `jsonpath_contains` / `jsonpath_gte` | inspect any field via kubectl-style `{.a.b[0].c}` paths |
| `field_absent` | assert a field was intentionally left unset |
| `pod_running` | Pod phase is `Running` |
| `replica_count` | a Deployment/ReplicaSet/StatefulSet has N ready replicas |
| `label_exists` / `annotation_exists` | metadata checks, with optional exact value |
| `container_image` | a (possibly named) container uses an image containing a given string |
| `container_resources` | a container declares a specific request/limit |
| `command_output_contains` / `command_output_not_contains` | run any shell command (e.g. `kubectl auth can-i ...`) and substring-match the output — the escape hatch for anything the structured checks don't cover |
| `manual` | learner self-attests (used for things that can't be cleanly auto-verified on a generic single-node lab, like etcd snapshot/restore or `kubectl top`) |

Adding a brand-new check type is a ~10-line method in `validator.py` named
`_check_<your_type>`; it's auto-discovered by name, no registration needed.

## What's included vs. what you might add

This ships with a solid, representative set of tasks across every official
CKA and CKAD domain — enough to actually drill the muscle memory for each
objective — but it isn't an exhaustive 1:1 replica of every possible exam
scenario. Because content is just YAML, it's meant to be extended: add more
tasks per objective, harder variations, or entirely new objectives (e.g.
Gateway API, Helm chart authoring, PodDisruptionBudgets) as you find gaps in
your own prep.
