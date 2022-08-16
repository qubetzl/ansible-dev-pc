#!/usr/bin/env bash
set -euo pipefail

ansible-vault decrypt vars/vault.yml
