#!/bin/bash
# Turn the simulator's own result into the Harbor reward.
#
# /evaluator/result.json was written inside the simulator's container when the
# episode was finished, and copied here by Harbor. If it is missing, something in
# the pipeline broke: fail loudly instead of reporting a score of zero.
set -euo pipefail

python3 /tests/grade.py \
    --result /evaluator/result.json \
    --reward /logs/verifier/reward.txt \
    --details /logs/verifier/lightlag-details.json
