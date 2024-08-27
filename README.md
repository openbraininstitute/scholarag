# Scholarag

A Retrieval Augmented Generation (RAG) API meant for scientific literature, which includes data management utilities and relevant endpoints for efficiently showcasing papers to your users.

0. [Quickstart](#quickstart)
1. [Setup](#setup)
2. [Database](#database)
3. [ETL Parsing](#etl-parsing)
4. [Funding and Acknowledgement](#funding-and-acknowledgement)

## Quickstart

Our API requires an Elascticsearch/Opensearch database to work, which can be quickly setup using the utilities we offer.

### Step 1: Download the package and start a simple Opensearch (or Elasticsearch) database using Docker.

The script `manage_index.py` can be used to create an index compatible with `scholarag`'s API requirements.

```bash
pip install scholarag
docker run -p 9200:9200 -it -d opensearchproject/opensearch:2.5.0 -Ediscovery.type=single-node -Eplugins.security.disabled=true
manage-index create pmc_paragraphs http://localhost:9200 -v
```

### Step 2: Start an XML parsing server.

The package `scholaretl` has been specifically made to be compatible with Scholarag. It offers an easy-to-use XML and PDF scientific article parsing (see [ETL Parsing](#etl-parsing)). A docker container can easily be started based as follow.

```bash
docker run -p 8080:8080 -d scholaretl:latest
```
The parsing API is reachable on port 8080.

### Step 3: Fill the database.

Multiple scripts are available to fill the database at different scales. A quick and efficient way to do it leverages the script `pmc_parse_and_upload.py`. It fetches all of the papers that PubMed Central uploaded on their s3 bucket on AWS. It is free and doesn't require an AWS account. Using it jointly with the parsing server deployed previously ensures correct formatting of the documents in the database.

```bash
pmc-parse-and-upload http://localhost:9200 http://localhost:8080/parse/jats_xml --start-date 01-01-1800 -v --batch-size=20
```

Specifying a distant start date prevents the search for matching documents to be too long. More details on the script can be found in the documentation [LINK]

### Step 4: Start the `scholarag-api`.

Create a `.env` file that sets the configuration of the scholarag API (see [Setup](#setup)).

```bash
vim .env
```
Required variables can be set up as such

```bash
SCHOLARAG__DB__DB_TYPE=opensearch
SCHOLARAG__DB__INDEX_PARAGRAPHS=pmc_paragraphs
SCHOLARAG__DB__HOST=http://localhost
SCHOLARAG__DB__PORT=9200
```
Such basic configuration unlocks the `Suggestions` and `Retrieval` endpoints. Simply add your OpenAI key under

```bash
SCHOLARAG__GENERATIVE__OPENAI__TOKEN=...
```
to unlock the `Question Answering` ones.

Finally, start the API.

```bash
scholarag-api
```

By default, it opens the API on port 8000. The swagger ui can be accessed at `http://localhost:8000/docs`

You can now interact with the API using HTTP requests. For example

```bash
curl http://localhost:8000/settings
```


## Setup

The `scholarag` API needs environment variables for configuration. Creating a `.env` file is recommended. A template is available under the file `.env.example`.
`scholarag` requires a database for every endpoint. DB specific variables can be set as follows:

```bash
# required
SCHOLARAG__DB__DB_TYPE= # elasticsearch or opensearch
SCHOLARAG__DB__INDEX_PARAGRAPHS= # name of the index containing the documents
SCHOLARAG__DB__HOST=
SCHOLARAG__DB__PORT=

# optional
SCHOLARAG__DB__INDEX_JOURNALS=
SCHOLARAG__DB__USER=
SCHOLARAG__DB__PASSWORD=
```

The variable `SCHOLARAG__DB__INDEX_JOURNALS` defines the name of the index containing the journals' impact factor information. While the variable is optional, the index can be created using the script `impact_factor.py` (TO BE CREATED).

Only setting the DB related variables unlocks the `Suggestions` and `Retrieval` endpoints. To unlock the `Question Answering` ones, the user must specify its OpenAI API key.

```bash
SCHOLARAG__GENERATIVE__OPENAI__TOKEN=sk-...
```

Our API relies on the `bm25` algorithm to retrieve documents from the database, since it is built for large databases and embedding every document would require a massive amount of storage. A reranking mecanism is implemented to compensate for the lack of transformer based semantic analysis. We leverage Cohere's reranker, which also requires an API key.

```bash
SCHOLARAG__RERANKING__COHERE_TOKEN=
```

While optional, the reranker typically improves greatly the retrieval's quality.

Finally, our API optionally supports `Redis` to cache potentially expensive requests. A redis container can be started locally using Docker

```bash
docker run -p 6379:6379 -d redis:latest
```

Redis related variables can be set as follow.

```bash
SCHOLARAG__REDIS__HOST=
SCHOLARAG__REDIS__PORT=
SCHOLARAG__REDIS__EXPIRY= # Time in days. Float.
```

The remaining environment variables are detailed in the documentation (LINK TO ENV VAR DOC).


## Database

The database is the cornerstone of the Scholarag API. We currently support Elasticsearch and Opensearch databases. The indices containing the documents need to have the following mapping in order to be compatible with the API.

```json
{
    "properties": {
        "article_id": {"type": "keyword"},
        "doi": {"type": "keyword"},
        "pmc_id": {"type": "keyword"},
        "pubmed_id": {"type": "keyword"},
        "arxiv_id": {"type": "keyword"},
        "title": {"type": "text"},
        "authors": {"type": "keyword"},
        "journal": {"type": "keyword"},
        "date": {"type": "date", "format": "yyyy-MM-dd"},
        "section": {"type": "keyword"},
        "paragraph_id": {"type": "short"},
        "text": {"type": "text"},
        "article_type": {"type": "keyword"},
    },
}
```
Multiple utilities are made available to fill de db. The external package `bbs-etl` (RENAME) offers a set of fully compatible parsers that convert raw papers into formatted JSONs ready to be inserted into the database. See [ETL Parsing](#etl-parsing) for more details.
The parsers can be directly used with the parsing and uploading scripts available in this project.

* `parse_and_upload.py`: Parses and uploads to DB documents downloaded locally.
```bash
parse-and-upload path parser_url db_url [OPTIONS]
```
* `pmc_parse_and_upload.py`: Parse and upload to DB documents downloaded from PMC's s3 bucket on AWS.
```bash
pmc-parse-and-upload db_url parser_url [OPTIONS]
```
* `pu_producer.py + pu_comsumer.py`: Producer and consumer logic leveraging AWS's SQS service to parse documents from any s3 bucket (requires access right to the bucket). Made for large scale document scraping.
```bash
pu-producer bucket_name queue_url [OPTIONS]
pu-consumer db_url pqrser_url queue_url [OPTIONS]
```

More info on parsing and uploading scripts available at (LINK TO SCRIPTS DOC).

## ETL Parsing

While the Scholarag API doesn't require any ETL logic per se, part of our package offers utilities to fill a database. `scholaretl` is a fully compatible ETL package offering mutliple parsers for scientific articles accessible through an API interface. The easiest way to get it started is through Docker.

```bash
docker run -p 8080:8080 -d scholaretl:latest
```

Optionally, a grobid server can be used to parse PDFs. It requires a Grobid server to be running. To deploy it, simply run

```bash
docker run -p 8070:8070 -d lfoppiano/grobid:0.7.3
```

and pass the server's URL as an environment variable

```bash
docker run -p 8080:8080 -d -e GROBID_URL=http://host.docker.internal:8070 scholaretl:latest
```

List of available endpoints:
* `/pubmed_xml`: parses XMLs coming from PubMed.
* `/jats_xml`: Parses XMLs coming from PMC.
* `/tei_xml`: Parses XMLs produced by Grobid.
* `/xocs_xml`: Parses XMLs coming from Scopus (Elsevier)
* `/pypdf_pdf`: Parses PDFs without keeping the structure of the document.
* `/grobid_pdf`: Parses PDFs keeping the structure of the document.

## Funding and Acknowledgement

The development of this software was supported by funding to the Blue Brain Project, a research center of the École polytechnique fédérale de Lausanne (EPFL), from the Swiss government’s ETH Board of the Swiss Federal Institutes of Technology.

Copyright (c) 2024 Blue Brain Project/EPFL
