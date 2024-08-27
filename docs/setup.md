# Application Setup

If one wants to run the application locally, it is needed to setup some environment variables first through
the CLI or an `.env` file.

## Mandatory environment variables

Here is the list of environment variables that needs to be set up to be able to launch the application:

- `SCHOLARAG__DB__DB_TYPE_`: the type of database used to store the articles. One can choose between `opensearch` or `elasticsearch`.
- `SCHOLARAG__DB__INDEX_PARAGRAPHS`: the name of the index where the articles are stored.
- `SCHOLARAG__DB__HOST`: host name of the OS/ES database.
- `SCHOLARAG__DB__PORT`: port of the OS/ES database.

## Optional environment variables

Here is the list of environment variables that can be set up:

#### Related to the OS/ES database

   - `SCHOLARAG__DB__INDEX_JOURNALS`: the name of the name where the journals are stored.
   - `SCHOLARAG__DB__USER`: if authentication is needed, specify here the username of the OS/ES database.
   - `SCHOLARAG__DB__PASSWORD`: if authentication is needed, specify here the password of the given username for the OS/ES database.

#### Related to the retrieval of the documents

   - `SCHOLARAG__RETRIEVAL__MAX_LENGTH`: maximum length of the documents to keep. By default, the value is 100000.

#### Related to the language model

Model `openai` is used for the LLM part, here are the environment variables to set up:

   - `SCHOLARAG__GENERATIVE__OPENAI__MODEL`: OpenAI model to use. By default, the model is `gpt-3.5-turbo`.
   - `SCHOLARAG__GENERATIVE__OPENAI__TOKEN`: OpenAI token.
   - `SCHOLARAG__GENERATIVE__OPENAI__TEMPERATURE`: Temperature of the model. By default, the temperature is 0.
   - `SCHOLARAG__GENERATIVE__OPENAI__MAX_TOKENS`: Maximum number of tokens for the language model to generate.

If one wants to have a custom prompt template:

   - `SCHOLARAG__GENERATIVE__PROMPT_TEMPLATE`: Custom prompt template, expect {SOURCES_SEPARATOR} and {ERROR_SEPARATOR}, for more details have a look at the default one present in generative_question_answering.py.

#### Related to the reranker

To use the `cohere reranker`, this environment variable needs to be set up:

   - `SCHOLARAG__RERANKING__COHERE__TOKEN`: the cohere token.

#### Related to the caching

If one wants to include some caching mechanisms:

   - `SCHOLARAG__REDIS__HOST`: the url of the caching database.
   - `SCHOLARAG__REDIS__PORT`: the port of the caching database.
   - `SCHOLARAG__REDIS__EXPIRY`: time in days for the expiration of the caching keys. By default, the value is 30.0.

#### Related to the logging

   - `SCHOLARAG__LOGGING__LEVEL`: the logging level of the application and the `scholarag` package logging. By default, the value is `info`.
   - `SCHOLARAG__LOGGING__EXTERNAL_PACKAGES`: the logging level of the external packages. By default, the value is `warning`.

#### Related to the retrieval of metadata of the documents

   - `SCHOLARAG__METADATA__EXTERNAL_APIS`: boolean to decide if there are retrieval of the metadata or not. By default, the value is `True`.
   - `SCHOLARAG__METADATA__TIMEOUT`: timeout of the metadata retrieval requests. By default, the value is 30.

#### Misc variables

   - `SCHOLARAG__MISC__APPLICATION_PREFIX`: Adds a prefix before every endpoint, which internally is removed by a middleware. Useful for instance for AWS application load balancer when using `path_patterns` conditions.
   - `SCHOLARAG__MISC__CORS_ORIGINS`: Specifies the cors origins to allow. Should be a string with comma separated values, i.e. `"value_1, value_2, ..."`.

#### Related to the keycloak authentication

   - `SCHOLARAG__KEYCLOAK__ISSUER`: Endpoint to use to check that the Keycloak token is valid.
   - `SCHOLARAG__KEYCLOAK__VALIDATE_TOKEN`: Boolean to decide if keycloak token should be validated or not.
### Sentry related

If ones want to setup sentry, it is also possible via `SENTRY_DSN` and `SENTRY_ENVIRONMENT`.