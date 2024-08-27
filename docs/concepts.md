# Basic concepts

In this documentation, we will explore important concepts related to various endpoints in our application.

## Client-side batching

## Error Codes

The QA endpoint uses error codes to communicate specific issues to users.
Codes 1,2,3 and 5,6 are associated with HTTP status code 500, while code 4 with HTTP status code 413.

#### No database entries found (code 1)

No relevant context was found in the database when using the QA or retrieval endpoints.

```json
{
    "detail": {
        "code": 1,
        "detail": "No document found. Modify the filters or the query and try again."
    }
}
```

#### No answer found during retrieval (code 2)

Relevant contexts were found in the database when using the QA or retrieval endpoints,
but the LLM could not give an answer based on these paragraphs.

```json
{
    "detail": {
        "code": 2,
        "detail": "The LLM did not provide any source to answer the question.",
        "raw_answer": "This is a raw answer."
    }
}
```

#### Endpoint is inactive (code 3)

On of the services used by the application is inactive, or one of the index names
is not set.

#### Input exceeded max tokens (code 4)

The input text's (The question + all the contexts sent) length is higher than
acceptable (the context window of the LLM might be the bottleneck).

```json
{
    "detail": {
        "code": 4,
        "detail": "OpenAI error."
    }
}
```

#### Maximum number of Cohere requests reached (code 5)

The maximum number of requests have been reached for the Cohere reranking model.

```json
{
    "detail": {
        "code": 5,
        "detail": "Max number of requests reached for Cohere reranker. Wait a little bit and try again, or disable the reranker."
    }
}
```

#### Answer is incomplete (code 6)

Maximum number of tokens was reached when generating an answer.

```json
{
    "detail": {
        "code": 6,
        "detail": "The LLM did not have enough completion tokens available to finish its answer. Please decrease the retriever_k value of 1 or 2.",
        "raw_answer": "Some raw answer."
    }
}
```

## Pipeline
