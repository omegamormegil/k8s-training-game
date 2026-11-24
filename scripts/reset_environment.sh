#!/usr/bin/env bash
# Wipes and recreates the 'game-lab' namespace that the learning game uses
# for its exercises. Cluster-scoped resources created by tasks (PVs,
# ClusterRoles, node taints/labels, etc.) are NOT touched — clean those up
# manually if a task's own cleanup command didn't cover them.
set -euo pipefail

: "${KUBECONFIG:=$HOME/.kube/k0s.config}"
export KUBECONFIG

echo "Using KUBECONFIG=$KUBECONFIG"
echo "Resetting namespace 'game-lab'..."
kubectl delete namespace game-lab --ignore-not-found
kubectl create namespace game-lab

echo "Done. 'game-lab' is now empty."
echo ""
echo "This does NOT reset saved progress in the game itself. Run:"
echo "    python main.py --reset-progress"
echo "if you also want to start the game from scratch."
