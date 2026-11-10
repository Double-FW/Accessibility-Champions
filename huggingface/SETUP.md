# Weekly Hugging Face update setup

Source: https://github.com/Double-FW/Accessibility-Champions

Destination: https://huggingface.co/datasets/GarethFW/Accessibility_Champions_Networks

The destination is already fixed in export-config.json. No HF_DATASET_ID variable
is required. Create a dataset-scoped Hugging Face token, then save it as repository
secret HF_TOKEN. Never put the token in a committed file. Create the workflow at
.github/workflows/huggingface-sync.yml using WORKFLOW_TO_COPY.txt in the setup ZIP.
Run it manually once and check its result. Weekly runs are Mondays at 07:23 UTC.

The export preserves source bytes, historical snapshot labels and notices. The
historical RAG reference is document-only to reduce duplicate section records.
New or renamed source files require review of the export configuration.
