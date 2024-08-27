# Scripts

Scholarag comes shipped with several handy scripts that help with filling up a database with documents used in the main API. They allow the user to parse and upload articles from several sources, while pre-defining the various fields in the DB that should contain article's metadata. Combined with the parsers offered in `bbs-etl`, they offer an easy solution to have a production grade database based on several data sources. There exist five main scripts:

```bash
create_impact_factor_index.py
manage_index.py
parse_and_upload.py
pmc_parse_and_upload.py
pu_producer.py + pu_consumer.py
```

## create_impact_factor_index.py

This script is creating the index containing impact factors of scientific journals. 
Data to populate the index should be saved under an excel file with the same schema as 
the one that can be found under `tests/data/citescore_sample.xlsx`.
This file can be asked to https://www.elsevier.com/products/scopus/metrics/citescore. 

Once the file is obtained, one can simply run the script by specifying the path to the file,
the name of the index one wants to have and the database where to save it.

After creating this index, one can use it in the application by specifying the environment
variable `SCHOLARAG__DB__INDEX_JOURNALS` with the new index name. Impact factors of the journals
are going to be given to the user when returning articles metadata.

```bash
positional arguments:
  from_file             Path to file containing impact factor information.
  index                 Name of the index to create.
  db_url                URL of the database instance. Format: HOST:PORT

options:
  -h, --help            show this help message and exit
  --db-type {elasticsearch,opensearch}
                        Type of database. (default: opensearch)
  --user USER           User of the database instance. The password is read from the environment under SCHOLARAG__DB__PASSWORD. (default: None)
  -v, --verbose         Control verbosity (default: False)
```

## manage_index.py

This script is a very simple database setup script. It allows for three concrete actions on a specific index: `create`, `delete`, `reset`.

- **create**: Create the specified index with a mapping compatible with what the main API expects, ready to receive documents from the parsers on `bbs-etl`. Several options can be provided to customise the index, but always within the usecase of the main API.

- **delete**: Simply delete the specified index if it exists.

- **reset**: Apply first delete, then create. It is a handy way to erase everything in your index for experimentation.

The remaining arguments of the script are typical arguments to point to the db, connect to it, and have a small customization capability. Here is an exhaustive list:

```bash
positional arguments:
  {create,delete,reset}
                        Specify the action to take. Reset = delete -> create.
  index                 Name of the index to deal with.
  db_url                URL of the database instance. Format: HOST:PORT

options:
  -h, --help            show this help message and exit
  --db-type {elasticsearch,opensearch}
                        Type of database. (default: elasticsearch)
  --user USER           User of the database instance. The password is read from the environment under SCHOLARAG__DB__PASSWORD. (default: None)
  --embed-name EMBED_NAME
                        Name of the embedding field. (default: embed_multi-qa-mpnet-base-dot-v1:1_0_0)
  --embed-dims EMBED_DIMS
                        Dimension of the embedding vectors. (default: 768)
  --n-shards N_SHARDS   Number of shards for the index. (default: 2)
  --n-replicas N_REPLICAS
                        Number of replicas for the index. (default: 1)
  -v, --verbose         Control verbosity (default: False)
```
The password of the database, if it exists, should be set in the environment under the variable name `SCHOLARAG__DB__PASSWORD`.


## parse_and_upload.py

This script parses local files (on your computer) and uploads them to the database you point to. It leverages the parsers in `bbs-etl` to extract the information from your xml/pdf files as well as the mapping provided by `manage_index.py`. Make sure to create an index using the latter before running this script. Here is an exhaustive list of the script's arguments:

```bash
positional arguments:
  path                  File or directory where are located the articles to parse.
  parser_url            URL of the parser (needs to contain this address and the parser).
  db_url                URL of the database instance (together with the port).

options:
  -h, --help            show this help message and exit
  --articles-per-bulk ARTICLES_PER_BULK
                        Maximum number of articles to process before sending them to the db. (default: 1000)
  --multipart-params MULTIPART_PARAMS
                        Dictionary for the multipart parameters for parsers that require some. Must be passed as a json formated dict. (default: None)
  --max-concurrent-requests MAX_CONCURRENT_REQUESTS
                        Maximum number of articles sent to the etl server PER BATCH OF 'articles-per-bulk' articles. (default: 10)
  --db-type {elasticsearch,opensearch}
                        Type of database. (default: opensearch)
  --user USER           User of the database instance. The password is read from the environment under SCHOLARAG__DB__PASSWORD. (default: None)
  --index INDEX         Desired name of the index holding paragraphs. (default: paragraphs)
  --files-failing-path FILES_FAILING_PATH
                        Path where to dump the files that failed. Expects a file. (default: None)
  -m MATCH_FILENAME, --match-filename MATCH_FILENAME
                        Parse only files with a name matching the given regular expression. Ignored when 'input_path' is a path to a file. (default: None)
  -r, --recursive       Parse files recursively. (default: False)
  --use-ssl             Whether to verify ssl certificates or not. (default: False)
  -v, --verbose         Control verbosity (default: False)
```
The parser specified under `parser_url` MUST contain the endpoint, which means that one must carefully select the correct parser for their data. For instance, xmls originating from PMC should use the `jats_xml` parser. Xmls originating from scopus must use the `xocs_xml` parser. Pdfs should use the `grobid_pdf` parser and so on. Please refer to the `bbs-etl` documentation for more information.

## pmc_parse_and_upload.py

This script is very similar to `parse_and_upload.py`, except that it doesn't use local files but rather fetches the files located in the public AWS s3 bucket of PMC. This bucket contains an up to date dump of the entirety of PMC (representing at this time roughly 6M articles). It uses `boto3` and `aiobotocore` to fetch and download files from the s3 bucket, and doesn't require any specific permission or access. It is a great way to download rapidly a big volume of data for experimentation.  It leverages the parsers in `bbs-etl` to extract the information from the xmls as well as the mapping provided by `manage_index.py`. Make sure to create an index using the latter before running this script. Here is an exhaustive list of the script's arguments:

```bash
positional arguments:
  db_url                URL of the database instance (together with the port).
  parser_url            URL of the parser (needs to contain the host:port and the parser type).

options:
  -h, --help            show this help message and exit
  --start-date START_DATE
                        Date of the oldest document to download. Format: dd-mm-yyy. (default: None)
  --batch-size BATCH_SIZE
                        Maximum number of articles to process before sending them to the db. (default: 500)
  --multipart-params MULTIPART_PARAMS
                        Dictionary for the multipart parameters for parsers that require some. Must be passed as a json formated dict. (default: None)
  --max-concurrent-requests MAX_CONCURRENT_REQUESTS
                        Maximum number of articles sent to the etl server PER BATCH OF 'articles-per-bulk' articles. (default: 10)
  --db-type {elasticsearch,opensearch}
                        Type of database. (default: opensearch)
  --user USER           User of the database instance. The password is read from the environment under SCHOLARAG__DB__PASSWORD. (default: None)
  --index INDEX         Desired name of the index holding paragraphs. (default: pmc_paragraphs)
  --files-failing-path FILES_FAILING_PATH
                        Path where to dump the files that failed. Expects a file. Not dumping if None. (default: None)
  --use-ssl             Whether to verify ssl certificates or not. (default: False)
  -v, --verbose         Control verbosity (default: False)
```
The correct parser endpoint to use for this script is `jats_xml` since every file originates from PMC. If `--start-date` remains `None`, it will be set to the previous day so that if you run this script automatically every day, you would always fetch the latest updates.

## pu_producer.py + pu_consumer.py

These scripts should be used together. They leverage an AWS service called SQS quich provides a queue service. They are the most efficient way to efficiently populate a production database with a huge amount of files.

### pu_producer.py

When it comes to using a queue service, the producer has the role of putting messages in the queue for the consumer to consume them. Here, the producer fetches articles in a specific AWS s3 bucket, gets the relevant article path, and forwards this information into the queue. It also includes a bunch of metadata into the message, so that the consumer knows what to do. Here is an exhaustive list of the script's arguments:

```bash
positional arguments:
  bucket_name           Url of the provider where to download the articles.
  queue_url             Url of the queue where to upload the articles.

options:
  -h, --help            show this help message and exit
  --index INDEX         Desired name of the index holding paragraphs. (default: pmc_paragraphs)
  --parser-name PARSER_NAME
                        Endpoint of the parser to use. Specify only if the s3 bucket is not ours. Else it will be fetch from the path. (default: None)
  --start-date START_DATE
                        Date of the oldest document to download. Format: dd-mm-yyy. (default: None)
  --prefixes PREFIXES [PREFIXES ...]
                        Prefix in the s3 path to filter the search on. Can write multiple prefixes to make it a list. (default: None)
  --sign-request        Sign the request with AWS credential. Should be activated for our bucket, not for public external buckets. (default: False)
  --file-extension FILE_EXTENSION
                        Extension of the file to enqueue. Leave None to parse any file type. (default: None)
  -v, --verbose         Control verbosity (default: False)
```

This script can work with any s3 bucket in theory. However if you point to a private s3 bucket, you need to sign your request with your AWS credentials using `--sign-request`. The `--prefixes` argument can be a list of partial paths inside of the s3 bucket, which will restrict the bucket crawling to the specified values. Finally `--file-extension` can be used to partially match the name of the files of interest, for instance by specifying only a certain type of files.
The `--parser-name` is of very specific interest. If you point this script towards an external s3 bucket (for instance the PMC one), it is likely that every file will need to be parsed with the same parser (e.g. `jats_xml` for the PMC bucket). However, to remain compatible with any data provider, even those not having an s3 bucket, we offer the possibility to infer the type of parser from the name of the folder containing the data. For instance assume that you have the five following parsers: `jats_xml`, `xocs_xml`, `grobid_pdf`, `pubmed_xml` and `core_json`. Assume that you have a private s3 bucket with the following layout:
```
my-s3-bucket
├── core_json
│   ├── file1.json
│   ├── file2.json
│
├── jats_xml
│   ├── file1.xml
│   ├── file2.xml
│
├── grobid_pdf
│   ├── file1.pdf
│   ├── file2.pdf
│
├── xocs_xml
│   ├── file1.xml
│   ├── file2.xml
│
├── pubmed_xml
│   ├── file1.xml
│   ├── file2.xml
```
If you run the script without providing `--parser-name` and pointing to this s3 bucket, each file will be sent to the queue alongside with the name of its parent folder as the parser to use for parsing. Therefore, one can download locally any file (compatible with the parsers) from any provider, and simply dump them in the s3 bucket under the correct folder for parsing.

### pu_consumer.py

The consumer script is complementary to the producer one. As soon as one runs the producer scripts, messages (articles) will be put in the sqs queue. The role of the consumer is to retrieve these messages, parse them and upload them to your database (that has a compatible index created using the `manage_index.py` script). Here is an exhaustive list of the script's arguments:

```bash
positional arguments:
  db_url                URL of the database instance (together with the port).
  parser_url            URL of the parser (needs to contain the host:port).
  queue_url             Url of the queue where to upload the articles.

options:
  -h, --help            show this help message and exit
  --batch-size BATCH_SIZE, -b BATCH_SIZE
                        Maximum number of articles to process before sending them to the db. (default: 500)
  --max-concurrent-requests MAX_CONCURRENT_REQUESTS
                        Maximum number of articles sent to the etl server PER BATCH OF 'articles-per-bulk' articles. (default: 10)
  --db-type {elasticsearch,opensearch}
                        Type of database. (default: opensearch)
  --user USER           User of the database instance. The password is read from the environment under SCHOLARAG__DB__PASSWORD. (default: None)
  --use-ssl             Whether to verify ssl certificates or not. (default: False)
  -v, --verbose         Control verbosity (default: False)
```
Here the `parser_url` MUST NOT contain the endpoint, since the endpoint is passed alongside with the message and is then retrieved individually for each message. The consumer script is a simple script that runs forever, doing what we call "long polling" of the queue. It will continuously listen to the queue, and process messages as soon as some are encountered in the queue. It implements multiprocessing capabilities to parallelize the processing of multiple messages at once. Typically useful to deploy it on a server and let it run continuously.
