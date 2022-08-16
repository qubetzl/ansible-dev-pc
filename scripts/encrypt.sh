#!/usr/bin/env bash
set -euo pipefail

ansible-vault encrypt vars/vault.yml
