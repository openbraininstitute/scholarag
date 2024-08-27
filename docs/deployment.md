# Application Deployment

The `scholarag` package contains an application that one can deploy.
To benefit from all the functionalities, some infrastructure needs to be deployed too:

- One needs first to deploy the application `scholarag` itself.
- A database containing the text content from scientific articles. The package currently supports `OpenSearch` and 
  `ElasticSearch` databases.
- (Optional) If the database needs to be populated, a tool parsing scientific articles is needed. 
  This is the case of `scholaretl` that is fully compatible with `scholarag`. 
  If `scholaretl` is used and some scientific papers are saved under `pdf` format, 
  one also needs to deploy a `grobid` server.
- (Optional) A database to be able to do caching. `Redis` is the only solution supported by `scholarag`.

To deploy everything, one needs first to create fill the two following environment variables
in the `compose.yaml` file.
```yaml
SCHOLARAG__DB__INDEX_PARAGRAPHS=TO_BE_SPECIFIED
SCHOLARAG__GENERATIVE__OPENAI__TOKEN=TO_BE_SPECIFIED
```

Once this is done, one can simply use `docker compose up` command from the root folder of the package:
```bash
docker compose up
```
Five containers are then spawn:
- `sholarag-app` containing the application that can be reached from `localhost:8080`.
- The opensearch database is deployed under `opensearchproject/opensearch:2.5.0` called `scholarag-opensearch-1` and reachable on `localhost:9200`. 
- `grobid/grobid:0.8.0` called `scholarag-grobid-1` being the grobid server reachable on `localhost:8070`.
- The redis instance called `scholarag-redis-1` reachable on `localhost:6379`.
- The ETL application `ETL IMAGE` called `scholarag-etl-1` reachable on port `9090`.

To destroy everything, one can simply use the following command:
```bash
docker compose down
```
If one keeps the volumes setup inside the `compose.yaml` file, the data inside the `opensearch` database 
is going to persist between different sessions. 

## Database population

To populate the database with data and to use all the functionalities of the `scholarag` application,
two indices need to be created: 
- One containing the text content to use for the question answering
- If text are coming from scientific papers, an index containing the impact factors of the different scientific journals.

Both indexes can be created and populated through two scripts (also deployed as endpoints) available in `scholarag` package.
For the first index, the script is `parse_and_upload.py` script (`pmc_parse_and_upload` can also be used if one wants to upload PMC papers
to the database). For the second, one can launch `create_impact_factor_index.py`. Please refers to the `scripts` documentation for 
further information. Both can be launched locally or after spawning a new docker container with the package installed with the 
following command line:
```bash
docker run -it --network=host scholarag-app /bin/bash
```

The flag `--network=host` is not mandatory but it is allowing a user to easily connect to
the database deployed by referring to it as `http://localhost:9200`.

As explained in the documentation, the script needs a `parser_url` as input. 
We recommend to use `scholaretl`, a package fully compatible with `scholarag`, to populate the first index. 
The purpose of the package is indeed to parse scientific articles with different formats and schemas (XML and PDF).
Launching `docker compose` is spawning this `scholaretl` application that is then directly usable.

The population of the database can then be launched using the following command (inside or outside a docker container):
```bash
pmc-parse-and-upload http://localhost:9200 http://localhost:9090/parse/jats_xml 
create-impact-factors-index file_name impact_factors http://localhost:9200
```
Note that the user needs to first create the index.
By default, the index is called `pmc_paragraphs` but it can be changed by adding the flag `--index`.

For the impact factor, one needs first to copy the file containing the information inside the docker 
if the script is launched inside the docker container. To copy it, one can launch the command:
```bash
docker cp file {DOCKER_CONTAINER}:/mnt
```