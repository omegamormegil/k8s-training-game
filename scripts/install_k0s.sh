#!/usr/bin/env bash
# Installs and starts a single-node k0s cluster (controller+worker combined),
# suitable for running the kubectl dojo learning game against.
#
# Tested on Ubuntu/Debian-family Linux. Requires sudo. Run as a regular user.
#
# k0s has no native macOS build, so on Darwin this delegates to
# install_k0s_macos.sh, which runs k0s inside a lightweight Lima Linux VM.
set -euo pipefail

if [ "$(uname -s)" = "Darwin" ]; then
    echo "Detected macOS — k0s doesn't ship a native macOS binary."
    echo "Running it inside a lightweight Linux VM via Lima instead..."
    echo ""
    exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/install_k0s_macos.sh"
fi

echo "==> Downloading and installing k0s..."
curl -sSLf https://get.k0s.sh | sudo sh

echo "==> Installing k0s as a single-node controller+worker..."
sudo k0s install controller --single

echo "==> Starting k0s..."
sudo k0s start

echo "==> Waiting for the API server to become ready..."
for i in $(seq 1 30); do
    if sudo k0s kubectl get --raw='/readyz' >/dev/null 2>&1; then
        echo "    API server is ready."
        break
    fi
    sleep 2
done

echo "==> Writing kubeconfig to ~/.kube/k0s.config..."
mkdir -p "$HOME/.kube"
sudo k0s kubeconfig admin > "$HOME/.kube/k0s.config"
sudo chown "$(id -u):$(id -g)" "$HOME/.kube/k0s.config"

echo ""
echo "============================================================"
echo " k0s is installed and running."
echo ""
echo " To use kubectl (and the learning game) against it, export:"
echo ""
echo "     export KUBECONFIG=\$HOME/.kube/k0s.config"
echo ""
echo " Add that line to your ~/.bashrc or ~/.zshrc to make it permanent."
echo ""
echo " Then verify with:"
echo "     kubectl get nodes"
echo "============================================================"
