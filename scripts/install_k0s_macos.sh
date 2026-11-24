#!/usr/bin/env bash
# Runs k0s on macOS inside a lightweight Linux VM managed by Lima
# (https://lima-vm.io). k0s itself has no native macOS build, so this is
# the standard way to run it locally on a Mac — the VM is small, boots in
# under a minute after the first image download, and kubectl on your Mac
# talks to it exactly like any other cluster once KUBECONFIG is set.
set -euo pipefail

INSTANCE_NAME="k0s"

if ! command -v brew >/dev/null 2>&1; then
    echo "Homebrew is required to install Lima and kubectl on macOS."
    echo "Install it from https://brew.sh and re-run this script."
    exit 1
fi

if ! command -v limactl >/dev/null 2>&1; then
    echo "==> Installing Lima (lightweight Linux VMs for macOS) via Homebrew..."
    brew install lima
fi

if ! command -v kubectl >/dev/null 2>&1; then
    echo "==> Installing kubectl via Homebrew..."
    brew install kubectl
fi

if limactl list --format '{{.Name}}' 2>/dev/null | grep -qx "$INSTANCE_NAME"; then
    echo "==> Lima instance '$INSTANCE_NAME' already exists."
    STATE=$(limactl list "$INSTANCE_NAME" --format '{{.Status}}' 2>/dev/null || echo "Unknown")
    if [ "$STATE" != "Running" ]; then
        echo "==> Starting it..."
        limactl start "$INSTANCE_NAME"
    fi
else
    echo "==> Creating and starting a k0s Lima VM."
    echo "    First run downloads a Linux image — this can take a few minutes."
    # Lima v2 uses 'template:k0s'; older versions use 'template://k0s'.
    limactl start --name="$INSTANCE_NAME" template:k0s || \
        limactl start --name="$INSTANCE_NAME" template://k0s
fi

echo "==> Locating the kubeconfig Lima exported from the VM..."
INSTANCE_DIR=$(limactl list "$INSTANCE_NAME" --format '{{.Dir}}')
GUEST_KUBECONFIG="$INSTANCE_DIR/copied-from-guest/kubeconfig.yaml"

for i in $(seq 1 20); do
    if [ -f "$GUEST_KUBECONFIG" ]; then
        break
    fi
    sleep 3
done

if [ ! -f "$GUEST_KUBECONFIG" ]; then
    echo ""
    echo "kubeconfig not found yet at:"
    echo "    $GUEST_KUBECONFIG"
    echo "The VM may still be finishing k0s setup. Check progress with:"
    echo "    limactl shell $INSTANCE_NAME -- sudo k0s status"
    echo "then re-run this script once that reports the cluster as up."
    exit 1
fi

mkdir -p "$HOME/.kube"
cp "$GUEST_KUBECONFIG" "$HOME/.kube/k0s.config"

echo ""
echo "============================================================"
echo " k0s is running inside a Lima VM named '$INSTANCE_NAME'."
echo ""
echo " To use kubectl (and the learning game) against it, export:"
echo ""
echo "     export KUBECONFIG=\$HOME/.kube/k0s.config"
echo ""
echo " Add that line to your ~/.zshrc to make it permanent (zsh is the"
echo " default shell on modern macOS)."
echo ""
echo " Then verify with:"
echo "     kubectl get nodes"
echo ""
echo " Useful Lima commands:"
echo "     limactl shell $INSTANCE_NAME     # SSH into the VM directly"
echo "     limactl stop $INSTANCE_NAME      # stop the VM"
echo "     limactl start $INSTANCE_NAME     # restart it later"
echo "     limactl delete $INSTANCE_NAME    # tear it down completely"
echo "============================================================"
