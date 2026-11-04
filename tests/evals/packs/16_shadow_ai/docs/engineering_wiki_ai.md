# Quartz Badger Media - Engineering Wiki: AI Tools (SYNTHETIC)

- Writers use OpenAI and Claude through a small internal web app; a Gemini key is used for image captions.
- The app is a LangChain script with function calling; it runs on a shared VM with no autoscaling.
- Known issues: the repo has a hardcoded API key and the API key in code is shared by the whole team; one prompt
  template puts credentials in prompt text so the agent can log into the CMS.
- No AI policy exists; nobody owns the model list. No evaluation set; no tracing; no content filter.
- Content and metadata live in a MySQL database and an Elasticsearch index with embeddings for semantic search.
- The CMS exposes a REST API and webhooks; there is no API gateway.
