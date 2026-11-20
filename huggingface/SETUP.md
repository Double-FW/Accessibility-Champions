# Weekly dataset updates

Source: https://github.com/Double-FW/Accessibility-Champions

Destination: https://huggingface.co/datasets/GarethFW/Accessibility_Champions_Networks

The [existing workflow](../.github/workflows/huggingface-sync.yml) supports manual runs and weekly updates on Mondays at 07:23 UTC. The destination is fixed in export-config.json; no HF_DATASET_ID variable is needed. Use the existing repository secret HF_TOKEN. Do not create or copy a new token for an ordinary documentation update, and never put credentials in a committed file.

## Publish an update

1. Publish the intended source documentation changes to main.
2. If a selected source changed, regenerate and commit the RAG reference, coverage and pack README using the instructions in the [resource pack](../Accessibility-Champions-RAG-and-Prompts/README.md). Review the activity prompts for affected assumptions or source routes.
3. Open the repository's Actions tab, select its Hugging Face update workflow and choose Run workflow for main, or allow the next scheduled run.
4. Check the completed run and the destination provenance before claiming the dataset contains the update. Scheduled execution can be delayed or disabled after inactivity.

The export preserves canonical text, source dates, attribution and evidence limits. It checks selected-source hashes and complete compiled bodies; a stale reference blocks publication rather than being labelled current. The compiled RAG reference is document-only to reduce duplicated section records. New or renamed canonical files require export-list review. Export checks establish packaging consistency, not editorial approval, audience evidence, programme adoption or legal compliance.
