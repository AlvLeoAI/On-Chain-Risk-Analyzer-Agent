# Evaluation Framework

This folder contains resources for evaluating the deterministic and probabilistic components of the On-Chain Fundamentals & Risk Analyzer.

## Folders
- `datasets/`: Ground truth JSON files mapping whitepaper texts to expected `ProjectProfile` extractions.
- `scripts/`: Scripts to run the `google-genai` agent against the datasets and compute accuracy/recall scores.
- `results/`: Output logs from evaluation runs.

## Process
1. A ground-truth dataset consists of unstructured text and the *expected* extracted fields.
2. The eval script runs the text through the `app.agent` parser.
3. It compares the structured `ProjectProfile` output against the expected fields to calculate performance metrics.
