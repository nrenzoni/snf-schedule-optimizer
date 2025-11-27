#!/bin/bash

GENERATED_DIR="../snf-schedule-optimizer-service/src/snf_schedule_optimizer/generated"

# Find all directories within the generated path and touch an empty __init__.py file in each
find "$GENERATED_DIR" -type d -exec touch {}/__init__.py \;
