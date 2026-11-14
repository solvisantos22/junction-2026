#!/bin/bash
set -euo pipefail
python3 /tests/grade.py --result /evaluator/result.json --reward /logs/verifier/reward.txt --details /logs/verifier/information-details.json
